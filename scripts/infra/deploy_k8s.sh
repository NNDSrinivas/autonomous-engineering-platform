#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE=${NAMESPACE:-navi-prod}

cd "$ROOT_DIR"

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.example.yaml -n "$NAMESPACE"
kubectl apply -f k8s/configmap.example.yaml -n "$NAMESPACE"

kubectl apply -f k8s/deployment.yaml -n "$NAMESPACE"
kubectl apply -f k8s/worker-deployment.yaml -n "$NAMESPACE"
kubectl apply -f k8s/service.yaml -n "$NAMESPACE"
kubectl apply -f k8s/ingress.yaml -n "$NAMESPACE"

kubectl apply -f k8s/migration-job.yaml -n "$NAMESPACE"
kubectl wait --for=condition=complete job/navi-migrate -n "$NAMESPACE" --timeout=300s

kubectl rollout status deployment/navi-backend -n "$NAMESPACE" --timeout=300s
kubectl rollout status deployment/navi-worker -n "$NAMESPACE" --timeout=300s

echo "[k8s] deploy complete"
