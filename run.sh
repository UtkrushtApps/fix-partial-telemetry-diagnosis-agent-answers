#!/usr/bin/env bash
set -euo pipefail

cd /root/task

echo "[run] Starting PostgreSQL via Docker Compose..."
docker compose up -d

echo "[run] Waiting for PostgreSQL to become healthy..."
for i in $(seq 1 30); do
  status="$(docker compose ps --format '{{.Health}}' postgres 2>/dev/null || true)"
  if echo "$status" | grep -qi healthy; then
    echo "[run] PostgreSQL is healthy."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[run] PostgreSQL did not become healthy in time." >&2
    docker compose logs postgres >&2 || true
    exit 1
  fi
  sleep 2
done

echo "[run] Performing database smoke check..."
python - <<'PY'
import os
os.environ.setdefault("DATABASE_URL", "postgresql://agent_user:agent_pass@127.0.0.1:5432/diagnosis_db")
from agent import db
assert db.db_smoke_check(), "smoke check failed"
print("[run] Database smoke check passed.")
PY

echo "[run] Running agent scaffold self-check..."
python -m agent --selfcheck

echo "Ready: PostgreSQL is healthy and the agent scaffold loads."

