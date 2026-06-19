"""Boundary layer between the telemetry tools and the LLM.

The functions here are responsible for turning raw tool outputs into the
reconciled, typed context the model reasons over, and for persisting a durable
record of each diagnosis.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from agent.config import config


OK_STATE = "ok"
STALE_STATE = "stale"
MISSING_STATE = "missing"
OFFLINE_STATE = "offline"
ERROR_STATE = "error"

FRESH_READ_STATES = {OK_STATE}
DEGRADED_READ_STATES = {OFFLINE_STATE, ERROR_STATE}
UNKNOWN_READ_STATES = {STALE_STATE, MISSING_STATE}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Some callers/providers use a trailing "Z" for UTC.  fromisoformat()
        # handles offsets but older Python versions do not accept bare Z.
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        dt = datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_status(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _age_seconds(recorded_at: datetime, now: datetime) -> int:
    # Treat slightly future-dated rows as fresh, while preserving the timestamp
    # itself for auditability.
    return max(0, int((now - recorded_at).total_seconds()))


def _base_read(kind: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    out: dict[str, Any] = {
        "type": kind,
        "state": ERROR_STATE,
        "available": False,
        "is_fresh": False,
        "recorded_at": raw.get("recorded_at"),
        "age_seconds": None,
        "freshness_budget_seconds": config.READING_FRESHNESS_SECONDS,
        "status": _safe_status(raw.get("status")),
        "reasons": [],
    }
    if kind == "sensor":
        out.update({
            "device_id": raw.get("device_id"),
            "temperature_c": raw.get("temperature_c"),
            "battery_pct": raw.get("battery_pct"),
        })
    else:
        out.update({
            "gateway_id": raw.get("gateway_id"),
            "uplink_ok": raw.get("uplink_ok"),
        })
    return out


def _classify_read(kind: str,
                   raw: dict[str, Any] | None,
                   now: datetime) -> dict[str, Any]:
    """Classify one raw telemetry tool result.

    State contract:
    - ok:      available, fresh, and reports online / gateway uplink healthy
    - stale:   available but outside the configured freshness window
    - missing: tool completed but no reading/status exists or timestamp needed
               to prove freshness is absent
    - offline: available and fresh, but the device/gateway reports offline or
               the gateway uplink is not OK
    - error:   malformed read, invalid timestamp, explicit error status, or an
               unrecognized status value
    """
    if not isinstance(raw, dict):
        read = _base_read(kind, None)
        read["reasons"].append("tool_result_not_an_object")
        return read

    read = _base_read(kind, raw)

    if raw.get("available") is not True:
        read["state"] = MISSING_STATE
        read["available"] = False
        read["reasons"].append(str(raw.get("reason") or "not_available"))
        return read

    read["available"] = True
    recorded_at = _parse_ts(raw.get("recorded_at"))
    if recorded_at is None:
        # Without a usable timestamp, the boundary layer cannot prove the read
        # is fresh.  Treat it as missing/unknown rather than letting the model
        # infer that a status value is current.
        read["state"] = MISSING_STATE
        read["is_fresh"] = False
        read["reasons"].append("missing_or_invalid_recorded_at")
        return read

    age = _age_seconds(recorded_at, now)
    read["recorded_at"] = recorded_at.isoformat()
    read["age_seconds"] = age
    read["is_fresh"] = age <= config.READING_FRESHNESS_SECONDS

    if not read["is_fresh"]:
        read["state"] = STALE_STATE
        read["reasons"].append("reading_is_stale")
        return read

    status = read["status"]
    if status == "online":
        if kind == "gateway" and raw.get("uplink_ok") is not True:
            read["state"] = OFFLINE_STATE
            read["reasons"].append("gateway_uplink_not_ok")
        else:
            read["state"] = OK_STATE
            read["reasons"].append("fresh_online")
        return read

    if status == "offline":
        read["state"] = OFFLINE_STATE
        read["reasons"].append("fresh_offline_status")
        return read

    if status == "error":
        read["state"] = ERROR_STATE
        read["reasons"].append("fresh_error_status")
        return read

    read["state"] = ERROR_STATE
    read["reasons"].append("missing_or_unrecognized_status")
    return read


def _overall_status(sensor: dict[str, Any], gateway: dict[str, Any]) -> str:
    sensor_state = sensor.get("state")
    gateway_state = gateway.get("state")

    if sensor_state in FRESH_READ_STATES and gateway_state in FRESH_READ_STATES:
        return "complete"

    # A fresh explicit offline/error signal means the system has known degraded
    # telemetry rather than merely unknown telemetry.
    if sensor_state in DEGRADED_READ_STATES or gateway_state in DEGRADED_READ_STATES:
        return "degraded"

    # Missing or stale reads mean current health cannot be established.
    return "unknown"


def _health_signal(overall_status: str) -> str:
    if overall_status == "complete":
        return "healthy_confirmed"
    if overall_status == "degraded":
        return "problem_detected_or_partial_failure"
    return "health_not_confirmed_unknown_telemetry"


def build_diagnosis_context(sensor_result: dict[str, Any],
                            gateway_result: dict[str, Any]) -> dict[str, Any]:
    """Reconcile raw sensor and gateway tool outputs into a typed context.

    The LLM must not perform freshness, completeness, partial-failure, or
    reconciliation logic itself.  This function converts the two raw tool
    outputs into a stable contract with one state per read and one overall
    completeness signal:

    - sensor/gateway.state is one of: ok, stale, missing, offline, error
    - overall_status is one of: complete, degraded, unknown
    - data_complete is true only when both reads are fresh successful reads

    A confirmed healthy diagnosis is only possible when the overall status is
    complete.  All stale, missing, offline, or error cases explicitly carry a
    non-complete status and data_complete=false.
    """
    now = _now()
    sensor = _classify_read("sensor", sensor_result, now)
    gateway = _classify_read("gateway", gateway_result, now)
    overall = _overall_status(sensor, gateway)
    data_complete = overall == "complete"

    blocking_reasons: list[str] = []
    for label, read in (("sensor", sensor), ("gateway", gateway)):
        state = read.get("state")
        if state != OK_STATE:
            reasons = ", ".join(read.get("reasons") or [])
            suffix = f" ({reasons})" if reasons else ""
            blocking_reasons.append(f"{label} read is {state}{suffix}")

    return {
        "schema_version": "telemetry-context/v1",
        "generated_at": now.isoformat(),
        "freshness_budget_seconds": config.READING_FRESHNESS_SECONDS,
        "sensor": sensor,
        "gateway": gateway,
        "overall_status": overall,
        "data_complete": data_complete,
        "telemetry_reliability": "complete" if data_complete else overall,
        "health_signal": _health_signal(overall),
        "can_confirm_healthy": data_complete,
        "blocking_reasons": blocking_reasons,
        "model_instructions": (
            "You may state that the device is healthy only when "
            "can_confirm_healthy is true and overall_status is complete. "
            "If can_confirm_healthy is false, lead with uncertainty and name "
            "the stale, missing, offline, or error telemetry."
        ),
    }


def render_context_for_model(context: dict[str, Any]) -> str:
    """Render the reconciled context into the message handed to the model.

    The rendering is intentionally explicit and JSON-backed so freshness and
    completeness distinctions cannot be collapsed into a vague prose summary.
    It also repeats the safety-critical diagnosis rule in plain language.
    """
    overall = context.get("overall_status")
    data_complete = context.get("data_complete")
    can_confirm_healthy = context.get("can_confirm_healthy")

    lines = [
        "STRICT RECONCILED TELEMETRY CONTEXT (computed in code; do not reinterpret raw tool results):",
        json.dumps(context, indent=2, sort_keys=True, default=str),
        "",
        f"Computed overall_status: {overall}",
        f"Computed data_complete: {data_complete}",
        f"Computed can_confirm_healthy: {can_confirm_healthy}",
    ]

    if not can_confirm_healthy:
        reasons = context.get("blocking_reasons") or ["telemetry is incomplete or degraded"]
        lines.extend([
            "MANDATORY DIAGNOSIS CONSTRAINT:",
            "Do NOT say the device is healthy, operating normally, or fully working.",
            "Lead with uncertainty and explain these limiting facts:",
        ])
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append(
            "MANDATORY DIAGNOSIS CONSTRAINT: Both reads are complete, fresh, and online; "
            "a concise healthy diagnosis is allowed."
        )

    return "\n".join(lines)

