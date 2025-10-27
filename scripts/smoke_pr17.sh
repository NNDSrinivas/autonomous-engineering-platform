#!/usr/bin/env bash
# Smoke test for PR-17 Memory Graph functionality
# Tests 3 core API endpoints with ENG-102 fixture data

set -e

# Configuration
CORE=${CORE:-"http://localhost:8000"}
ORG_ID=${ORG_ID:-"default"}
ISSUE=${ISSUE:-"ENG-102"}

echo "🧪 PR-17 Memory Graph Smoke Test"
echo "=================================="
echo "API URL:  $CORE"
echo "Org ID:   $ORG_ID"
echo "Test Issue: $ISSUE"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASS=0
FAIL=0

test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_field="$5"
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -H "X-Org-Id: $ORG_ID" "$CORE$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" -H "X-Org-Id: $ORG_ID" \
                   -H "Content-Type: application/json" -d "$data" "$CORE$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" != "200" ]; then
        echo -e "${RED}FAIL${NC} (HTTP $http_code)"
        echo "  Response: $body"
        ((FAIL++))
        return 1
    fi
    
    if [ -n "$expected_field" ]; then
        if echo "$body" | jq -e "$expected_field" > /dev/null 2>&1; then
            echo -e "${GREEN}PASS${NC}"
            ((PASS++))
            return 0
        else
            echo -e "${RED}FAIL${NC} (missing field: $expected_field)"
            echo "  Response: $body"
            ((FAIL++))
            return 1
        fi
    else
        echo -e "${GREEN}PASS${NC}"
        ((PASS++))
        return 0
    fi
}

# Test 1: Get node neighborhood
echo
echo "📍 Test 1: Get Node Neighborhood"
echo "GET /api/memory/graph/node/$ISSUE"
echo "---"
test_endpoint "Node neighborhood" "GET" "/api/memory/graph/node/$ISSUE" "" ".node.id"

if [ $? -eq 0 ]; then
    response=$(curl -s -H "X-Org-Id: $ORG_ID" "$CORE/api/memory/graph/node/$ISSUE")
    echo "  Root node: $(echo $response | jq -r '.node.foreign_id')"
    echo "  Neighbors: $(echo $response | jq '.neighbors | length')"
    echo "  Edges found: $(echo $response | jq '.edges | length')"
    echo "  Relations: $(echo $response | jq -r '.edges[].relation' | sort -u | tr '\n' ', ')"
fi

# Test 2: Get timeline
echo
echo "📅 Test 2: Get Timeline"
echo "GET /api/memory/timeline?entity_id=$ISSUE&window=30d"
echo "---"
test_endpoint "Timeline" "GET" "/api/memory/timeline?entity_id=$ISSUE&window=30d" "" ". | length >= 0"

if [ $? -eq 0 ]; then
    response=$(curl -s -H "X-Org-Id: $ORG_ID" "$CORE/api/memory/timeline?entity_id=$ISSUE&window=30d")
    echo "  Timeline items: $(echo $response | jq '. | length')"
    echo "  Sequence:"
    echo $response | jq -r '.[] | "    - \(.title) (\(.kind))"'
fi

# Test 3: Graph query with narrative
echo
echo "🔍 Test 3: Graph Query with Narrative"
echo "POST /api/memory/graph/query"
echo "---"
query_data='{"query":"Why was ENG-102 reopened and what was the fix?","depth":3,"k":12}'
test_endpoint "Graph query" "POST" "/api/memory/graph/query" "$query_data" ".narrative"

if [ $? -eq 0 ]; then
    response=$(curl -s -X POST -H "X-Org-Id: $ORG_ID" -H "Content-Type: application/json" \
               -d "$query_data" "$CORE/api/memory/graph/query")
    echo "  Nodes in subgraph: $(echo $response | jq '.nodes | length')"
    echo "  Edges in subgraph: $(echo $response | jq '.edges | length')"
    echo "  Narrative preview:"
    echo $response | jq -r '.narrative' | head -n 3 | sed 's/^/    /'
    if [ $(echo $response | jq -r '.narrative' | wc -l) -gt 3 ]; then
        echo "    ..."
    fi
fi

# Summary
echo
echo "=================================="
echo "Summary:"
echo -e "  ${GREEN}PASS: $PASS${NC}"
if [ $FAIL -gt 0 ]; then
    echo -e "  ${RED}FAIL: $FAIL${NC}"
fi
echo

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✅ All smoke tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed${NC}"
    exit 1
fi
