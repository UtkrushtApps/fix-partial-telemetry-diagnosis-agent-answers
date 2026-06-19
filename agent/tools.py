"""Tool implementations that wrap telemetry retrieval.

These are read-only data tools. Each returns a small structured result. When a
read cannot produce a value, it returns a structured 'missing' result rather
than raising, so the boundary layer can reconcile partial outcomes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent import db


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def get_sensor_status(device_id: str) -> dict[str, Any]:
    row = db.fetch_latest_sensor_reading(device_id)
    if row is None:
        return {"available": False, "reason": "no_reading", "device_id": device_id}
    return {
        "available": True,
        "device_id": row["device_id"],
        "status": row["status"],
        "temperature_c": float(row["temperature_c"]) if row["temperature_c"] is not None else None,
        "battery_pct": float(row["battery_pct"]) if row["battery_pct"] is not None else None,
        "recorded_at": _iso(row["recorded_at"]),
    }


def get_gateway_status(gateway_id: str) -> dict[str, Any]:
    row = db.fetch_latest_gateway_status(gateway_id)
    if row is None:
        return {"available": False, "reason": "no_status", "gateway_id": gateway_id}
    return {
        "available": True,
        "gateway_id": row["gateway_id"],
        "status": row["status"],
        "uplink_ok": row["uplink_ok"],
        "recorded_at": _iso(row["recorded_at"]),
    }


TOOL_REGISTRY = {
    "get_sensor_status": get_sensor_status,
    "get_gateway_status": get_gateway_status,
}

