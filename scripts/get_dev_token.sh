#!/bin/bash
# Helper script to get a dev token for testing
#
# Usage:
#   1. Print token only (for command substitution):
#      export NAVI_TEST_TOKEN="$(bash scripts/get_dev_token.sh --quiet)"
#
#   2. Interactive mode with messages:
#      bash scripts/get_dev_token.sh
#
#   3. Source to auto-export:
#      source scripts/get_dev_token.sh

set -e

BASE_URL="${PUBLIC_BASE_URL:-http://127.0.0.1:8787}"
QUIET_MODE=false

# Parse arguments
if [[ "$1" == "--quiet" ]] || [[ "$1" == "-q" ]]; then
    QUIET_MODE=true
fi

# Helper function for logging
log() {
    if [[ "$QUIET_MODE" != true ]]; then
        echo "$@" >&2
    fi
}

log "🔐 Getting dev token from $BASE_URL..."

# Start device flow
log "📱 Starting device flow..."
RESPONSE=$(curl -s -X POST "$BASE_URL/oauth/device/start" \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -d '{"client_id":"aep-vscode-extension","scope":"read write"}')

DEVICE_CODE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['device_code'])")
USER_CODE=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['user_code'])")

log "   Device code: $DEVICE_CODE"
log "   User code: $USER_CODE"

# Approve
log "✅ Approving device..."
curl -s -X POST "$BASE_URL/oauth/device/authorize" \
  -H "Content-Type: application/json" \
  -d "{\"user_code\":\"$USER_CODE\",\"action\":\"approve\",\"user_id\":\"test-user\",\"org_id\":\"default\"}" > /dev/null

# Poll for token
log "🔄 Polling for token..."
TOKEN_RESPONSE=$(curl -s -X POST "$BASE_URL/oauth/device/poll" \
  -H "Content-Type: application/json" \
  -d "{\"device_code\":\"$DEVICE_CODE\"}")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# If sourced, export it automatically
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    export NAVI_TEST_TOKEN="$ACCESS_TOKEN"
    log "✅ NAVI_TEST_TOKEN exported to current shell"
elif [[ "$QUIET_MODE" == true ]]; then
    # Quiet mode: print only the token
    echo "$ACCESS_TOKEN"
else
    # Interactive mode: print with instructions
    log "✨ Token obtained successfully!"
    log ""
    log "Export this token:"
    echo "export NAVI_TEST_TOKEN=\"$ACCESS_TOKEN\""
fi
