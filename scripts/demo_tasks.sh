#!/usr/bin/env bash
set -euo pipefail

CORE_PORT="${CORE_PORT:-8002}"
REALTIME_PORT="${REALTIME_PORT:-8001}"

# 1) Create a meeting session and captions like PR-3 demo
resp=$(curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions" \
  -H "Content-Type: application/json" -d '{"title":"Eng Sync","provider":"manual"}')
sid=$(echo "$resp" | python - <<'PY'
import sys, json; print(json.load(sys.stdin)["session_id"])
PY)
echo "Session: $sid"

# 2) Post a caption that clearly contains an action
curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions/${sid}/captions" \
  -H "Content-Type: application/json" \
  -d '{"text":"Action: Implement JWT expiry check PR #42 and close JIRA-123", "speaker":"Lead"}' >/dev/null

# 3) Finalize meeting -> worker summarizes and creates action items; tasks auto-created
curl -s -X POST "http://localhost:${CORE_PORT}/api/meetings/${sid}/finalize" | jq

echo "Waiting for processing..."
sleep 4

# 4) Query tasks
echo "Tasks:"
curl -s "http://localhost:${CORE_PORT}/api/tasks?status=open" | jq

# 5) Update a task to done
tid=$(curl -s "http://localhost:${CORE_PORT}/api/tasks" | jq -r '.items[0].id')
curl -s -X PATCH "http://localhost:${CORE_PORT}/api/tasks/${tid}" -H "Content-Type: application/json" -d '{"status":"done"}' | jq

# 6) Stats
echo "Stats:"
curl -s "http://localhost:${CORE_PORT}/api/tasks/stats/summary" | jq