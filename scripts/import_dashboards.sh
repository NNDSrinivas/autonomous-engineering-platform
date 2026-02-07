#!/bin/bash
# Quick script to import all Grafana dashboards
# Usage: ./scripts/import_dashboards.sh

set -e

GRAFANA_URL="http://localhost:3001"
GRAFANA_USER="admin"
GRAFANA_PASS="admin"

echo "📊 Importing NAVI Dashboards to Grafana..."
echo "Grafana URL: $GRAFANA_URL"
echo ""

# Function to import a dashboard
import_dashboard() {
    local file=$1
    local name=$(basename "$file" .json)

    echo -n "Importing $name... "

    # Wrap the dashboard JSON in the required format
    local payload=$(jq -n --slurpfile dashboard "$file" '{
        dashboard: $dashboard[0],
        overwrite: true,
        message: "Imported via script"
    }')

    response=$(curl -s \
        -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d "$payload" \
        "$GRAFANA_URL/api/dashboards/db")

    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d "$payload" \
        "$GRAFANA_URL/api/dashboards/db")

    body="$response"

    if [ "$http_code" -eq 200 ]; then
        dashboard_url=$(echo "$body" | jq -r '.url // empty')
        echo "✅ Success!"
        if [ -n "$dashboard_url" ]; then
            echo "   → $GRAFANA_URL$dashboard_url"
        fi
    else
        echo "❌ Failed (HTTP $http_code)"
        echo "   Response: $body"
    fi
}

# Check if Grafana is accessible
echo "Checking Grafana connection..."
if ! curl -s -f -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/health" > /dev/null; then
    echo "❌ Cannot connect to Grafana at $GRAFANA_URL"
    echo "Please ensure Grafana is running: docker ps | grep grafana"
    exit 1
fi
echo "✅ Grafana is accessible"
echo ""

# Import all dashboards
echo "Importing dashboards..."
echo ""

import_dashboard "grafana/dashboards/navi-llm-metrics.json"
import_dashboard "grafana/dashboards/navi-task-metrics.json"
import_dashboard "grafana/dashboards/navi-errors.json"
import_dashboard "grafana/dashboards/navi-learning.json"

echo ""
echo "✅ Dashboard import complete!"
echo ""
echo "View dashboards at:"
echo "  • LLM Metrics: $GRAFANA_URL/d/navi-llm/navi-llm-performance-metrics"
echo "  • Task Metrics: $GRAFANA_URL/d/navi-tasks/navi-task-execution-metrics"
echo "  • Error Tracking: $GRAFANA_URL/d/navi-errors/navi-error-tracking"
echo "  • Learning System: $GRAFANA_URL/d/navi-learning/navi-learning-feedback-system"
echo ""
echo "Next steps:"
echo "  1. Configure data sources (Prometheus + PostgreSQL)"
echo "  2. Generate test data: make e2e-validation-quick"
echo "  3. View real-time metrics in dashboards"
