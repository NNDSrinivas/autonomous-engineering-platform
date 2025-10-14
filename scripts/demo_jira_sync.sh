#!/usr/bin/env bash
set -euo pipefail
CORE_PORT="${CORE_PORT:-8002}"

# 1) Connect (MVP token-based)
resp=$(curl -s -X POST "http://localhost:${CORE_PORT}/api/integrations/jira/connect" \
 -H "Content-Type: application/json" \
 -d '{"cloud_base_url":"https://YOUR.atlassian.net","access_token":"REDACTED"}')
cid=$(echo "$resp" | python -c 'import sys,json; print(json.load(sys.stdin)["connection_id"])')

# 2) Config
curl -s -X POST "http://localhost:${CORE_PORT}/api/integrations/jira/config" \
 -H "Content-Type: application/json" \
 -d '{"connection_id":"'"$cid"'","project_keys":["PROJ"],"default_jql":""}' | jq

# 3) Sync
curl -s -X POST "http://localhost:${CORE_PORT}/api/integrations/jira/sync?connection_id=${cid}" | jq
echo "Enqueued. Start worker: python -m backend.workers.integrations"
