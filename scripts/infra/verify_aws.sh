#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform/aws"

cd "$TF_DIR"
ALB_DNS=$(terraform output -raw alb_dns_name)

if [ -z "$ALB_DNS" ]; then
  echo "[aws] missing ALB DNS output"
  exit 1
fi

echo "[aws] checking http://$ALB_DNS/health"
curl -fsS "http://$ALB_DNS/health" > /dev/null

echo "[aws] health ok"
