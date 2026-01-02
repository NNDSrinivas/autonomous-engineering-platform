#!/usr/bin/env bash
# Quick health check for NAVI backend
# Usage: scripts/backend_health.sh [BASE_URL]
# Default BASE_URL: http://127.0.0.1:8787

set -euo pipefail

BASE_URL="${1:-${AEP_BACKEND_URL:-http://127.0.0.1:8787}}"
URL="${BASE_URL%/}/api/navi/chat"

payload='{"message":"health_check","attachments":[],"workspace_root":null}'

echo "Hitting ${URL}"
http_code=$(curl -s -o /tmp/aep_health_out.txt -w "%{http_code}" \
  -H "Content-Type: application/json" \
  --data "${payload}" \
  "${URL}" || true)

echo "HTTP ${http_code}"
echo "Response (first 300 chars):"
head -c 300 /tmp/aep_health_out.txt
echo

if [[ "${http_code}" != "200" ]]; then
  echo "Health check failed"
  exit 1
fi
