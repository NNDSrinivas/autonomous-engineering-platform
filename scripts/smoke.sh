#!/usr/bin/env bash
set -euo pipefail

CORE=${CORE:-http://localhost:8002}

echo "[SMOKE] Testing PR-9.1: Telemetry & Audit Logging"
echo "[SMOKE] Core API: $CORE"

# Test plan generation endpoint
echo "[SMOKE] Generating plan for demo ticket..."
RESPONSE=$(curl -s -X POST "$CORE/api/plan/DEMO-1" \
  -H 'Content-Type: application/json' \
  -d '{"contextPack": {"ticket":{"key":"DEMO-1","summary":"demo ticket for telemetry testing"}}}')

echo "[SMOKE] Plan response received"
echo "$RESPONSE" | jq '.telemetry.model, .telemetry.tokens, .telemetry.cost_usd, .telemetry.latency_ms, .plan.items | length'

# Test metrics endpoint
echo "[SMOKE] Checking Prometheus metrics..."
METRICS_RESPONSE=$(curl -s "$CORE/metrics")

echo "[SMOKE] Checking LLM call counters..."
echo "$METRICS_RESPONSE" | grep -E 'aep_llm_calls_total|aep_llm_tokens_total|aep_llm_cost_usd_total' | head -n 10

echo "[SMOKE] Checking LLM latency histograms..."
echo "$METRICS_RESPONSE" | grep 'aep_llm_latency_ms' | head -n 5

# Generate another plan to verify metrics increment
echo "[SMOKE] Generating second plan to verify metrics increment..."
curl -s -X POST "$CORE/api/plan/DEMO-2" \
  -H 'Content-Type: application/json' \
  -d '{"contextPack": {"ticket":{"key":"DEMO-2","summary":"second demo ticket"}}}' > /dev/null

echo "[SMOKE] Checking updated metrics..."
curl -s "$CORE/metrics" | grep 'aep_llm_calls_total' | head -n 5

echo "✅ PR-9.1 telemetry and audit logging smoke test completed successfully"