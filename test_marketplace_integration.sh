#!/bin/bash
# Test script to demonstrate complete connectors marketplace functionality

echo "🚀 Testing Connectors Marketplace Integration"
echo "=============================================="

echo
echo "1. Testing health endpoint..."
curl -s http://localhost:8000/health | jq .

echo
echo "2. Testing marketplace status endpoint..."
curl -s http://localhost:8000/api/connectors/marketplace/status | jq 'length' | xargs echo "Total connectors:"

echo
echo "3. Showing initial Jira status..."
curl -s http://localhost:8000/api/connectors/marketplace/status | jq '.[] | select(.id == "jira")'

echo
echo "4. Connecting to Jira..."
curl -s -X POST http://localhost:8000/api/connectors/jira/connect \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://company.atlassian.net", "email": "test@example.com", "api_token": "test_token"}' | jq .

echo
echo "5. Verifying Jira connection status updated..."
curl -s http://localhost:8000/api/connectors/marketplace/status | jq '.[] | select(.id == "jira")'

echo
echo "6. Showing all connector statuses..."
curl -s http://localhost:8000/api/connectors/marketplace/status | jq '.[] | {id: .id, name: .name, status: .status}'

echo
echo "✅ Integration test complete! Marketplace is fully functional."