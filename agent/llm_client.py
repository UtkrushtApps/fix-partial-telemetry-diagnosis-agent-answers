"""Real LLM client wrapper built on litellm.

This file is complete and is NOT the candidate's main work. It calls a real
provider model when a key is present. It is the planning/reasoning component of
the agent.
"""
from __future__ import annotations

import json
from typing import Any

import litellm

from agent.config import config


class LLMError(RuntimeError):
    pass


def chat(messages: list[dict[str, Any]],
         tools: list[dict[str, Any]] | None = None,
         temperature: float = 0.1) -> dict[str, Any]:
    """Call the real model and return the raw assistant message as a dict.

    Returns a dict with keys: 'content' (str|None) and 'tool_calls' (list|None).
    """
    if not config.has_provider_key():
        raise LLMError(
            "No provider key found. Set OPENAI_API_KEY (or another supported "
            "provider key) in your .env to run the real agent."
        )
    try:
        resp = litellm.completion(
            model=config.LLM_MODEL,
            messages=messages,
            tools=tools,
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"Model call failed: {exc}") from exc

    choice = resp["choices"][0]["message"]
    tool_calls = None
    raw_calls = choice.get("tool_calls")
    if raw_calls:
        tool_calls = []
        for tc in raw_calls:
            fn = tc["function"]
            args = fn.get("arguments") or "{}"
            try:
                parsed = json.loads(args)
            except json.JSONDecodeError:
                parsed = {}
            tool_calls.append({
                "id": tc.get("id"),
                "name": fn["name"],
                "arguments": parsed,
            })
    return {"content": choice.get("content"), "tool_calls": tool_calls}


def ping_model() -> str:
    """Lightweight key-gated model ping used by the self-check only."""
    out = chat(
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        tools=None,
    )
    return out.get("content") or ""

