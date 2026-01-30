#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform/aws"

if [ "${CONFIRM_DESTROY:-}" != "1" ]; then
  echo "[aws] set CONFIRM_DESTROY=1 to destroy terraform resources"
  exit 1
fi

cd "$TF_DIR"

terraform destroy -auto-approve
