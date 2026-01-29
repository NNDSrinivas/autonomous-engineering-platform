#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL=${1:-"http://127.0.0.1:8787/health"}

for i in {1..10}; do
  if curl -fsS "$HEALTH_URL" > /dev/null 2>&1; then
    echo "[local] health ok: $HEALTH_URL"
    exit 0
  fi
  sleep 1
  if [ $i -eq 10 ]; then
    echo "[local] health check failed: $HEALTH_URL"
    exit 1
  fi
done
