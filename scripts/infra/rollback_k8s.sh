#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-navi-prod}

kubectl rollout undo deployment/navi-backend -n "$NAMESPACE"
kubectl rollout undo deployment/navi-worker -n "$NAMESPACE"

kubectl rollout status deployment/navi-backend -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/navi-worker -n "$NAMESPACE" --timeout=300s

echo "[k8s] rollback complete"
