#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-navi-prod}
API_URL=${API_URL:-""}

kubectl get pods -n "$NAMESPACE"
kubectl rollout status deployment/navi-backend -n "$NAMESPACE" --timeout=120s
kubectl rollout status deployment/navi-worker -n "$NAMESPACE" --timeout=120s

if [ -n "$API_URL" ]; then
  echo "[k8s] checking health at $API_URL"
  curl -fsS "$API_URL/health" > /dev/null
fi

