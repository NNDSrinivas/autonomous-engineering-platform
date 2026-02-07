#!/bin/bash
# Update Grafana URLs in dashboards and alert rules
# Usage: ./scripts/update_grafana_urls.sh <grafana-url>

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <grafana-url>"
    echo ""
    echo "Examples:"
    echo "  $0 http://localhost:3000                                    # Local dev"
    echo "  $0 https://grafana.navi.com                                 # Self-hosted"
    echo "  $0 https://g-abc123.grafana-workspace.us-east-1.amazonaws.com  # AWS Managed"
    echo "  $0 https://yourcompany.grafana.net                          # Grafana Cloud"
    exit 1
fi

GRAFANA_URL="$1"

echo "🔧 Updating Grafana URLs to: $GRAFANA_URL"
echo ""

# Update Grafana dashboards
echo "📊 Updating Grafana dashboards..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|http://grafana:3000|$GRAFANA_URL|g" grafana/dashboards/*.json
else
    # Linux
    sed -i "s|http://grafana:3000|$GRAFANA_URL|g" grafana/dashboards/*.json
fi

# Update Prometheus alert rules
echo "🚨 Updating Prometheus alert rules..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|http://grafana:3000|$GRAFANA_URL|g" prometheus/alerts/navi-slos.yaml
else
    # Linux
    sed -i "s|http://grafana:3000|$GRAFANA_URL|g" prometheus/alerts/navi-slos.yaml
fi

echo ""
echo "✅ Done! Updated Grafana URL in:"
echo "   - grafana/dashboards/*.json (4 files)"
echo "   - prometheus/alerts/navi-slos.yaml"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Test dashboards: Import into Grafana"
echo "  3. Commit changes: git add . && git commit -m 'Update Grafana URLs'"
