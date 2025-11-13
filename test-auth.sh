#!/bin/bash
# Test script for AEP OAuth device flow

echo "🧪 Testing AEP OAuth Device Flow"
echo "================================="

# Start device code flow
echo "1. Starting device code flow..."
RESPONSE=$(curl -s -X POST http://localhost:8000/oauth/device/start \
  -H "Content-Type: application/json" \
  -d '{"client_id": "aep-vscode-extension", "scope": "read write"}')

echo "Response: $RESPONSE"

# Extract device code
DEVICE_CODE=$(echo $RESPONSE | jq -r '.device_code')
USER_CODE=$(echo $RESPONSE | jq -r '.user_code')

if [ "$DEVICE_CODE" = "null" ]; then
    echo "❌ Failed to get device code"
    exit 1
fi

echo "✅ Device code: ${DEVICE_CODE:0:8}..."
echo "✅ User code: $USER_CODE"

# Poll for authorization (will auto-approve after 30 seconds)
echo "2. Waiting for auto-approval (30+ seconds)..."
for i in {1..40}; do
    echo -n "."
    sleep 2
    
    POLL_RESPONSE=$(curl -s -X POST http://localhost:8000/oauth/device/poll \
      -H "Content-Type: application/json" \
      -d "{\"device_code\": \"$DEVICE_CODE\", \"client_id\": \"aep-vscode-extension\"}")
    
    if echo $POLL_RESPONSE | grep -q "access_token"; then
        echo ""
        echo "✅ Authentication successful!"
        ACCESS_TOKEN=$(echo $POLL_RESPONSE | jq -r '.access_token')
        echo "Access token: ${ACCESS_TOKEN:0:8}..."
        
        # Test API endpoints with token
        echo "3. Testing API endpoints..."
        
        echo "Testing /api/me..."
        curl -s -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/me | jq .
        
        echo "Testing /api/integrations/jira/my-issues..."
        curl -s -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/integrations/jira/my-issues | jq .
        
        exit 0
    fi
done

echo ""
echo "❌ Authentication timed out"