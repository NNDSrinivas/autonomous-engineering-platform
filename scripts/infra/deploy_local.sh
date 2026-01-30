#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="/tmp/aep_local.pid"
API_HOST=${API_HOST:-127.0.0.1}
API_PORT=${API_PORT:-8787}
HEALTH_URL=${HEALTH_URL:-"http://${API_HOST}:${API_PORT}/health"}

cd "$ROOT_DIR"

echo "[local] starting dependencies via docker compose..."
docker compose up -d

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "[local] backend already running (pid $(cat "$PID_FILE"))"
  exit 0
fi

echo "[local] starting backend..."
export APP_ENV=${APP_ENV:-development}
export API_HOST
export API_PORT

nohup python3 -m backend.api.main > /tmp/aep_local.log 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"

for i in {1..15}; do
  sleep 1
  if curl -fsS "$HEALTH_URL" > /dev/null 2>&1; then
    echo "[local] backend healthy at $HEALTH_URL"
    exit 0
  fi
  if [ $i -eq 15 ]; then
    echo "[local] backend failed to start"
    tail -n 200 /tmp/aep_local.log || true
    exit 1
  fi
done
