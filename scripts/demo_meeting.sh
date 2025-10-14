#!/usr/bin/env bash
set -euo pipefail

CORE_PORT="${CORE_PORT:-8000}"      # you may be using 8002 locally
REALTIME_PORT="${REALTIME_PORT:-8001}"

echo "Creating session..."
resp=$(curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions" -H "Content-Type: application/json" -d '{"title":"Sprint Planning","provider":"manual"}')
echo "$resp"
sid=$(echo "$resp" | python -c 'import sys,json; print(json.load(sys.stdin)["session_id"])')

echo "Posting captions..."
post() { curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions/${sid}/captions" -H "Content-Type: application/json" -d "$1" >/dev/null; }
post '{"text":"Welcome team, today we finalize sprint scope.","speaker":"PM","ts_start_ms":0,"ts_end_ms":2000}'
post '{"text":"Action: implement JWT expiry check in AuthService.","speaker":"Lead","ts_start_ms":2000,"ts_end_ms":5000}'
post '{"text":"We agreed to move payment retries to next sprint.","speaker":"PM"}'
post '{"text":"Risk: flaky integration tests on checkout flow.","speaker":"QA"}'
post '{"text":"TODO: add monitoring alert for 5xx spike.","speaker":"SRE"}'

echo "Finalizing..."
curl -s -X POST "http://localhost:${CORE_PORT}/api/meetings/${sid}/finalize" | jq

echo "Waiting for worker (4s)..."
sleep 4

echo "Summary:"
curl -s "http://localhost:${CORE_PORT}/api/meetings/${sid}/summary" | jq

echo "Actions:"
curl -s "http://localhost:${CORE_PORT}/api/meetings/${sid}/actions" | jq
