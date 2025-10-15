#!/usr/bin/env bash
set -euo pipefail

CORE_PORT="${CORE_PORT:-8002}"
REALTIME_PORT="${REALTIME_PORT:-8001}"

echo "=== PR-5: Real-time Answer Coach Demo ==="
echo ""

# 1) Create session
echo "1. Creating session..."
resp=$(curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions" -H "Content-Type: application/json" -d '{"title":"Standup","provider":"manual"}')
sid=$(echo "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin)["session_id"])')
echo "   Session ID: $sid"
echo ""

# 2) Post some context + a question
echo "2. Posting captions with context..."
post() { 
    curl -s -X POST "http://localhost:${REALTIME_PORT}/api/sessions/${sid}/captions" \
        -H "Content-Type: application/json" \
        -d "$1" >/dev/null
    echo "   Posted: $(echo "$1" | python3 -c 'import sys,json; print(json.load(sys.stdin)["text"])')"
}

# Replace ISSUE-123 with your actual project issue key as needed
post '{"text":"We worked on ISSUE-123 and fixed the retry loop."}'
post '{"text":"JWT expiry is parsed in auth layer per last sprint."}'
post '{"text":"Where is the JWT expiry parsed now?"}'
echo ""

# 3) Poll answers (few times)
echo "3. Polling for answers (6 attempts, 1s apart)..."
for i in {1..6}; do
  echo ""
  echo "   Poll $i:"
  resp=$(curl -s -w "%{http_code}" "http://localhost:${REALTIME_PORT}/api/sessions/${sid}/answers")
  body="${resp::-3}"
  status="${resp: -3}"
  if [[ "$status" != "200" ]]; then
    echo "   [API error] HTTP status: $status"
  elif ! echo "$body" | python3 -m json.tool 2>/dev/null; then
    echo "   [JSON parse error] Invalid JSON response"
  fi
  sleep 1
done

echo ""
echo "=== Demo Complete ==="
echo "Check that answers appeared with citations!"
