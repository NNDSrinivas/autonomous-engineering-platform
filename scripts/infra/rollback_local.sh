#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/tmp/aep_local.pid"

if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "[local] stopping backend pid $PID"
    kill "$PID" || true
  fi
  rm -f "$PID_FILE"
fi

echo "[local] stopping dependencies (docker compose)"
docker compose down

