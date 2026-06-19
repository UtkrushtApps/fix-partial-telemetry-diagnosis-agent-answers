#!/usr/bin/env bash
set -euo pipefail

echo "[kill] Starting cleanup..."

if [ -d /root/task ]; then
  echo "[kill] Entering /root/task..."
  cd /root/task
else
  echo "[kill] /root/task not found; continuing."
fi

echo "[kill] Stopping Docker Compose services..."
docker compose down --remove-orphans || true

echo "[kill] Removing Docker Compose volumes..."
docker compose down -v --remove-orphans || true
docker volume rm task_pgdata || true

echo "[kill] Removing task Docker networks..."
docker network rm task_default || true

echo "[kill] Removing task Docker images (if any)..."
docker rmi -f postgres:16 || true

echo "[kill] Pruning Docker system..."
docker system prune -a --volumes -f || true

echo "[kill] Removing /root/task..."
rm -rf /root/task || true

echo "Cleanup completed successfully!"

