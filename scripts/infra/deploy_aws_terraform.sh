#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform/aws"

if [ "${CONFIRM_APPLY:-}" != "1" ]; then
  echo "[aws] set CONFIRM_APPLY=1 to apply terraform"
  exit 1
fi

cd "$TF_DIR"

terraform init
terraform plan -out tfplan
terraform apply tfplan
