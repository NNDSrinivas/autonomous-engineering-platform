#!/bin/bash
# PR-19 Smoke Test: Live Plan Mode + Real-Time Collaboration
# Tests basic plan lifecycle: create → add steps → archive

set -e

# Configuration
ORG="test-org-123"
API="${CORE:-http://localhost:8000}"
BOLD="\033[1m"
GREEN="\033[0;32m"
RED="\033[0;31m"
BLUE="\033[0;34m"
RESET="\033[0m"

echo -e "${BOLD}${BLUE}🧪 PR-19 Smoke Test: Live Plan Mode${RESET}"
echo "Testing API: $API"
echo "Organization: $ORG"
echo ""

# Check if API is running
echo -e "${BOLD}1. Checking API health...${RESET}"
if ! curl -s "$API/health" > /dev/null 2>&1; then
  echo -e "${RED}❌ API not responding at $API${RESET}"
  echo "   Start the backend with: make pr19-dev"
  exit 1
fi
echo -e "${GREEN}✅ API is running${RESET}"
echo ""

# Test 1: Create Plan
echo -e "${BOLD}2. Creating plan session...${RESET}"
CREATE_RESPONSE=$(curl -s -X POST "$API/api/plan/start" \
  -H "X-Org-Id: $ORG" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Smoke Test Plan",
    "description": "Testing plan creation and collaboration",
    "participants": ["user1", "user2"]
  }')

PLAN_ID=$(echo "$CREATE_RESPONSE" | jq -r '.plan_id')
STATUS=$(echo "$CREATE_RESPONSE" | jq -r '.status')

if [ "$STATUS" != "started" ] || [ -z "$PLAN_ID" ] || [ "$PLAN_ID" == "null" ]; then
  echo -e "${RED}❌ Failed to create plan${RESET}"
  echo "   Response: $CREATE_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✅ Plan created${RESET}"
echo "   Plan ID: $PLAN_ID"
echo ""

# Test 2: Get Plan Details
echo -e "${BOLD}3. Retrieving plan details...${RESET}"
GET_RESPONSE=$(curl -s "$API/api/plan/$PLAN_ID" -H "X-Org-Id: $ORG")

TITLE=$(echo "$GET_RESPONSE" | jq -r '.title')
if [ "$TITLE" != "Smoke Test Plan" ]; then
  echo -e "${RED}❌ Failed to retrieve plan${RESET}"
  echo "   Response: $GET_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✅ Plan retrieved${RESET}"
echo "   Title: $TITLE"
echo "   Participants: $(echo "$GET_RESPONSE" | jq -r '.participants | join(", ")')"
echo ""

# Test 3: Add Steps
echo -e "${BOLD}4. Adding plan steps...${RESET}"

STEPS=(
  '{"plan_id":"'"$PLAN_ID"'","text":"Design API endpoints","owner":"user1"}'
  '{"plan_id":"'"$PLAN_ID"'","text":"Implement authentication","owner":"user2"}'
  '{"plan_id":"'"$PLAN_ID"'","text":"Write unit tests","owner":"user1"}'
)

for i in "${!STEPS[@]}"; do
  STEP_NUM=$((i + 1))
  STEP_RESPONSE=$(curl -s -X POST "$API/api/plan/step" \
    -H "X-Org-Id: $ORG" \
    -H "Content-Type: application/json" \
    -d "${STEPS[$i]}")
  
  STEP_STATUS=$(echo "$STEP_RESPONSE" | jq -r '.status')
  if [ "$STEP_STATUS" != "step_added" ]; then
    echo -e "${RED}❌ Failed to add step $STEP_NUM${RESET}"
    echo "   Response: $STEP_RESPONSE"
    exit 1
  fi
  
  STEP_TEXT=$(echo "$STEP_RESPONSE" | jq -r '.step.text')
  echo -e "   ${GREEN}✅ Step $STEP_NUM:${RESET} $STEP_TEXT"
done

echo -e "${GREEN}✅ All steps added${RESET}"
echo ""

# Test 4: Verify Steps Saved
echo -e "${BOLD}5. Verifying steps persisted...${RESET}"
VERIFY_RESPONSE=$(curl -s "$API/api/plan/$PLAN_ID" -H "X-Org-Id: $ORG")
STEP_COUNT=$(echo "$VERIFY_RESPONSE" | jq '.steps | length')

if [ "$STEP_COUNT" != "3" ]; then
  echo -e "${RED}❌ Expected 3 steps, found $STEP_COUNT${RESET}"
  exit 1
fi

echo -e "${GREEN}✅ Steps verified${RESET}"
echo "   Total steps: $STEP_COUNT"
echo ""

# Test 5: List Plans
echo -e "${BOLD}6. Listing active plans...${RESET}"
LIST_RESPONSE=$(curl -s "$API/api/plan/list?archived=false" -H "X-Org-Id: $ORG")
PLAN_COUNT=$(echo "$LIST_RESPONSE" | jq '.count')

if [ -z "$PLAN_COUNT" ] || [ "$PLAN_COUNT" == "null" ]; then
  echo -e "${RED}❌ Failed to list plans${RESET}"
  echo "   Response: $LIST_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✅ Plans listed${RESET}"
echo "   Active plans: $PLAN_COUNT"
echo ""

# Test 6: Archive Plan
echo -e "${BOLD}7. Archiving plan...${RESET}"
ARCHIVE_RESPONSE=$(curl -s -X POST "$API/api/plan/$PLAN_ID/archive" \
  -H "X-Org-Id: $ORG")

ARCHIVE_STATUS=$(echo "$ARCHIVE_RESPONSE" | jq -r '.status')
MEMORY_NODE_ID=$(echo "$ARCHIVE_RESPONSE" | jq -r '.memory_node_id // empty')

if [ "$ARCHIVE_STATUS" != "archived" ]; then
  echo -e "${RED}❌ Failed to archive plan${RESET}"
  echo "   Response: $ARCHIVE_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✅ Plan archived${RESET}"
if [ -n "$MEMORY_NODE_ID" ]; then
  echo "   Memory node ID: $MEMORY_NODE_ID"
fi
echo ""

# Test 7: Verify Archive Status
echo -e "${BOLD}8. Verifying archive status...${RESET}"
ARCHIVED_RESPONSE=$(curl -s "$API/api/plan/$PLAN_ID" -H "X-Org-Id: $ORG")
ARCHIVED=$(echo "$ARCHIVED_RESPONSE" | jq -r '.archived')

if [ "$ARCHIVED" != "true" ]; then
  echo -e "${RED}❌ Plan not marked as archived${RESET}"
  exit 1
fi

echo -e "${GREEN}✅ Archive status verified${RESET}"
echo ""

# Test 8: List Archived Plans
echo -e "${BOLD}9. Listing archived plans...${RESET}"
ARCHIVED_LIST=$(curl -s "$API/api/plan/list?archived=true" -H "X-Org-Id: $ORG")
ARCHIVED_COUNT=$(echo "$ARCHIVED_LIST" | jq '.count')

echo -e "${GREEN}✅ Archived plans listed${RESET}"
echo "   Archived count: $ARCHIVED_COUNT"
echo ""

# Summary
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${GREEN}✅ All Smoke Tests Passed!${RESET}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "${BOLD}Test Summary:${RESET}"
echo "  ✅ Plan creation"
echo "  ✅ Plan retrieval"
echo "  ✅ Step addition (3 steps)"
echo "  ✅ Step persistence"
echo "  ✅ Plan listing"
echo "  ✅ Plan archiving"
echo "  ✅ Archive status"
echo "  ✅ Archived plan listing"
echo ""
echo -e "${BOLD}Plan Details:${RESET}"
echo "  Plan ID: $PLAN_ID"
echo "  Steps: $STEP_COUNT"
echo "  Status: Archived ✅"
if [ -n "$MEMORY_NODE_ID" ]; then
  echo "  Memory Node: $MEMORY_NODE_ID"
fi
echo ""
echo -e "${BLUE}🎉 PR-19 Live Plan Mode is working correctly!${RESET}"
