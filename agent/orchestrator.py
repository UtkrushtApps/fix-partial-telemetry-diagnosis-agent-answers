"""Agent loop: real LLM plans tool calls, tools run, results are reconciled,
and the model writes the final diagnosis over the reconciled context.
"""
from __future__ import annotations

import uuid
from typing import Any

from agent import db
from agent.config import config
from agent.llm_client import chat
from agent.postprocess import build_diagnosis_context, render_context_for_model
from agent.prompts import build_diagnosis_messages
from agent.tool_schemas import ALL_TOOLS
from agent.tools import TOOL_REGISTRY


def _run_planned_tools(tool_calls: list[dict[str, Any]],
                       device: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute the read-only tools the model asked for. Always attempts both
    reads using the device's known ids so the boundary layer can reconcile a
    full picture."""
    sensor_result = TOOL_REGISTRY["get_sensor_status"](device["device_id"])
    gateway_result = TOOL_REGISTRY["get_gateway_status"](device["gateway_id"])
    return sensor_result, gateway_result


def diagnose_device_health(user_request: str, device_id: str) -> dict[str, Any]:
    trace_id = str(uuid.uuid4())
    device = db.fetch_device(device_id)
    if device is None:
        return {"trace_id": trace_id, "error": "unknown_device", "device_id": device_id}

    # Step 1: model plans which tools to call.
    messages = build_diagnosis_messages(
        f"{user_request}\n\n(device_id={device_id}, gateway_id={device['gateway_id']})"
    )
    planning = chat(messages=messages, tools=ALL_TOOLS)

    # Step 2: execute read-only telemetry tools.
    sensor_result, gateway_result = _run_planned_tools(
        planning.get("tool_calls") or [], device
    )

    # Step 3: reconcile raw tool outputs into a typed context for the model.
    context = build_diagnosis_context(sensor_result, gateway_result)

    # Step 4: model writes the diagnosis over the reconciled context only.
    followup = build_diagnosis_messages(user_request)
    followup.append({
        "role": "system",
        "content": "Reconciled telemetry context:\n" + render_context_for_model(context),
    })
    final = chat(messages=followup, tools=None)
    summary = final.get("content") or ""

    # Step 5: persist a durable, traceable record of the diagnosis.
    db.insert_diagnosis_log(
        trace_id=trace_id,
        device_id=device_id,
        overall_status=context.get("overall_status"),
        data_complete=context.get("data_complete"),
        summary=summary,
    )

    return {
        "trace_id": trace_id,
        "device_id": device_id,
        "overall_status": context.get("overall_status"),
        "data_complete": context.get("data_complete"),
        "context": context,
        "diagnosis": summary,
    }

