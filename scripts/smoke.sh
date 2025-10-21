#!/bin/bash
set -euo pipefail

CORE=${CORE:-http://localhost:8002}

echo "[SMOKE] Testing PR-9.1: Telemetry & Audit Logging"
echo "[SMOKE] Core API: $CORE"

# Test plan generation endpoint
echo "[SMOKE] Generating plan for demo ticket..."
RESPONSE=$(curl -sf -X POST "$CORE/api/plan/DEMO-1" \
  -H 'Content-Type: application/json' \
  -d '{"contextPack": {"ticket":{"key":"DEMO-1","summary":"demo ticket for telemetry testing"}}}')

echo "[SMOKE] Plan response received"
echo "[SMOKE] Telemetry model:      $(echo "$RESPONSE" | jq -r '.telemetry.model')"
echo "[SMOKE] Telemetry tokens:     $(echo "$RESPONSE" | jq -r '.telemetry.tokens')"
echo "[SMOKE] Telemetry cost (USD): $(echo "$RESPONSE" | jq -r '.telemetry.cost_usd')"
echo "[SMOKE] Telemetry latency (ms): $(echo "$RESPONSE" | jq -r '.telemetry.latency_ms')"
echo "[SMOKE] Plan items count:     $(echo "$RESPONSE" | jq -r '.plan.items | length')"

# Test metrics endpoint
echo "[SMOKE] Checking Prometheus metrics..."
METRICS_RESPONSE=$(curl -sf "$CORE/metrics")

# Constants for metrics display (can be overridden via environment)
METRICS_DISPLAY_LIMIT=${METRICS_DISPLAY_LIMIT:-10}
LATENCY_DISPLAY_LIMIT=${LATENCY_DISPLAY_LIMIT:-5}

echo "[SMOKE] Checking LLM call counters..."
echo "$METRICS_RESPONSE" | grep -E 'aep_llm_calls_total|aep_llm_tokens_total|aep_llm_cost_usd_total' | head -n $METRICS_DISPLAY_LIMIT

echo "[SMOKE] Checking LLM latency histograms..."
echo "$METRICS_RESPONSE" | grep 'aep_llm_latency_ms' | head -n $LATENCY_DISPLAY_LIMIT

# Generate another plan to verify metrics increment
echo "[SMOKE] Generating second plan to verify metrics increment..."
# Temporarily disable exit on failure for this curl command
set +e
SECOND_RESPONSE=$(curl -sf -X POST "$CORE/api/plan/DEMO-2" \
  -H 'Content-Type: application/json' \
  -d '{"contextPack": {"ticket":{"key":"DEMO-2","summary":"second demo ticket"}}}')
CURL_EXIT_CODE=$?
set -e

if [ $CURL_EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Second plan generation failed with exit code $CURL_EXIT_CODE"
    echo "[ERROR] Response: $SECOND_RESPONSE"
    exit $CURL_EXIT_CODE
fi

echo "[SMOKE] Second plan generated successfully"

echo "[SMOKE] Checking updated metrics..."
curl -s "$CORE/metrics" | grep 'aep_llm_calls_total' | head -n 5

echo "✅ PR-9.1 telemetry and audit logging smoke test completed successfully"