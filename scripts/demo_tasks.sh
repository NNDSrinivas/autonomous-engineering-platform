#!/usr/bin/env bash
set -euo pipefail

CORE_PORT="${CORE_PORT:-8002}"
REALTIME_PORT="${REALTIME_PORT:-8001}"

resp=$(curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions" \
  -H "Content-Type: application/json" \
  -d '{"title":"Eng Sync","provider":"manual"}')
sid=$(echo "$resp" | python - <<'PY'
import json, sys
print(json.load(sys.stdin)["session_id"])
PY
)
echo "Session: $sid"

curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions/${sid}/captions" \
  -H "Content-Type: application/json" \
  -d '{"text":"Action: Implement JWT expiry check PR #42 and close JIRA-123","speaker":"Lead"}' >/dev/null

curl -s -X POST "http://localhost:${CORE_PORT}/api/meetings/${sid}/finalize" | jq

echo "Waiting for processing..."
sleep 4

echo "Tasks:"
curl -s "http://localhost:${CORE_PORT}/api/tasks?status=open" | jq

tid=$(curl -s "http://localhost:${CORE_PORT}/api/tasks" | jq -r '.items[0].id')
curl -s -X PATCH "http://localhost:${CORE_PORT}/api/tasks/${tid}" \
  -H "Content-Type: application/json" \
  -d '{"status":"done"}' | jq

echo "Stats:"
curl -s "http://localhost:${CORE_PORT}/api/tasks/stats/summary" | jq
