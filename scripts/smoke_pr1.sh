#!/usr/bin/env bash
set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Use virtual environment executables
VENV_ALEMBIC="$PROJECT_DIR/.venv/bin/alembic"

echo "🔧 Infra"
docker compose ps

echo "🧱 Alembic"
"$VENV_ALEMBIC" current || true
"$VENV_ALEMBIC" upgrade head

echo "🚀 Core API"
curl -sf http://localhost:8002/health | jq '.service,.status'
curl -sf http://localhost:8002/version | jq '.name,.version'

echo "⚡ Realtime API"
curl -sf http://localhost:8001/health | jq '.service,.status'
curl -sf http://localhost:8001/version | jq '.name,.version'

echo "✅ Smoke passed"
