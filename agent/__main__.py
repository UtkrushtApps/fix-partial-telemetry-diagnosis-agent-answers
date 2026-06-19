"""CLI entry point and self-check for the diagnosis agent."""
from __future__ import annotations

import argparse
import sys

from agent import db
from agent.config import config
from agent.prompts import SYSTEM_PROMPT
from agent.tool_schemas import ALL_TOOLS


def _selfcheck() -> int:
    print("[selfcheck] Loading configuration...")
    assert config.DATABASE_URL, "DATABASE_URL missing"
    assert config.READING_FRESHNESS_SECONDS > 0, "freshness budget must be positive"

    print("[selfcheck] Verifying tool schemas...")
    names = {t["function"]["name"] for t in ALL_TOOLS}
    assert {"get_sensor_status", "get_gateway_status"} <= names, "tools missing"

    print("[selfcheck] Verifying system prompt loads...")
    assert "SYSTEM POLICY" in SYSTEM_PROMPT, "system prompt missing policy"

    print("[selfcheck] Checking database connectivity and seed data...")
    assert db.db_smoke_check(), "database smoke check failed"

    if config.has_provider_key():
        print("[selfcheck] Provider key found; pinging model directly...")
        from agent.llm_client import ping_model
        out = ping_model()
        print(f"[selfcheck] Model responded: {out!r}")
    else:
        print("[selfcheck] No provider key set; skipping model ping (set one in .env to run the agent).")

    print("[selfcheck] OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IoT device diagnosis agent")
    parser.add_argument("--selfcheck", action="store_true", help="run scaffold self-check")
    parser.add_argument("--device", help="device_id to diagnose")
    parser.add_argument("--request", default="Is my device working?", help="customer request")
    args = parser.parse_args()

    if args.selfcheck:
        return _selfcheck()

    if not args.device:
        print("Provide --device <device_id> or --selfcheck", file=sys.stderr)
        return 2

    from agent.orchestrator import diagnose_device_health
    result = diagnose_device_health(args.request, args.device)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

