"""Candidate-facing invariant tests for the tool-to-model boundary.

These tests do not call the model. They verify that raw tool outputs are
reconciled into an honest, typed context and rendered without losing the
completeness/freshness distinctions. They are NOT run by run.sh.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from agent.config import config
from agent.postprocess import build_diagnosis_context, render_context_for_model


def _iso(seconds_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def _fresh_sensor():
    return {
        "available": True, "device_id": "dev-100", "status": "online",
        "temperature_c": 22.4, "battery_pct": 88, "recorded_at": _iso(30),
    }


def _fresh_gateway(status="online"):
    return {
        "available": True, "gateway_id": "gw-001", "status": status,
        "uplink_ok": status == "online", "recorded_at": _iso(20),
    }


def test_complete_when_both_fresh_and_online():
    ctx = build_diagnosis_context(_fresh_sensor(), _fresh_gateway())
    assert ctx["overall_status"] == "complete"
    assert ctx["data_complete"] is True
    assert ctx["sensor"]["state"] == "ok"
    assert ctx["gateway"]["state"] == "ok"


def test_degraded_when_gateway_offline():
    ctx = build_diagnosis_context(_fresh_sensor(), _fresh_gateway(status="offline"))
    assert ctx["overall_status"] == "degraded"
    assert ctx["data_complete"] is False


def test_missing_read_is_marked_missing():
    missing = {"available": False, "reason": "no_status", "gateway_id": "gw-002"}
    ctx = build_diagnosis_context(_fresh_sensor(), missing)
    assert ctx["gateway"]["state"] == "missing"
    assert ctx["overall_status"] in ("degraded", "unknown")
    assert ctx["data_complete"] is False


def test_stale_read_is_not_treated_as_fresh():
    stale_age = config.READING_FRESHNESS_SECONDS + 600
    stale_sensor = {
        "available": True, "device_id": "dev-300", "status": "online",
        "temperature_c": 19.8, "battery_pct": 60, "recorded_at": _iso(stale_age),
    }
    stale_gateway = {
        "available": True, "gateway_id": "gw-003", "status": "online",
        "uplink_ok": True, "recorded_at": _iso(stale_age),
    }
    ctx = build_diagnosis_context(stale_sensor, stale_gateway)
    assert ctx["sensor"]["state"] == "stale"
    assert ctx["gateway"]["state"] == "stale"
    assert ctx["overall_status"] != "complete"
    assert ctx["data_complete"] is False


def test_rendered_context_preserves_distinctions():
    ctx = build_diagnosis_context(_fresh_sensor(), _fresh_gateway(status="offline"))
    rendered = render_context_for_model(ctx)
    assert isinstance(rendered, str) and rendered.strip()
    low = rendered.lower()
    # The degraded/incomplete signal must survive into the model-facing text.
    assert ("degraded" in low) or ("incomplete" in low) or ("offline" in low)
    assert ctx["overall_status"] in low

