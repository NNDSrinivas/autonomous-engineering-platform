#!/usr/bin/env bash
set -euo pipefail
CORE_PORT="${CORE_PORT:-8002}"

# 1) Connect
resp=$(curl -s -X POST "http://localhost:${CORE_PORT}/api/integrations/github/connect" \
 -H "Content-Type: application/json" \
 -d '{"access_token":"REDACTED"}')
cid=$(echo "$resp" | python -c 'import sys,json; print(json.load(sys.stdin)["connection_id"])')

# 2) Index repo
curl -s -X POST "http://localhost:${CORE_PORT}/api/github/index" \
 -H "Content-Type: application/json" \
 -d '{"connection_id":"'"$cid"'","repo_full_name":"octocat/Hello-World"}' | jq

echo "Enqueued. Start worker: python -m backend.workers.integrations"
