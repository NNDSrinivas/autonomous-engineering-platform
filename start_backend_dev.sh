#!/bin/bash
# Start backend with dev environment variables

export DEV_USER_ID="dev-user-1"
export DEV_USER_EMAIL="srinivasn7779@gmail.com"
export DEV_ORG_ID="default-org"
export DEV_USER_ROLE="admin"

# Allow dev auth bypass for local development
export ALLOW_DEV_AUTH_BYPASS=true

cd /Users/mounikakapa/dev/autonomous-engineering-platform

# Load .env file if it exists
if [ -f ".env" ]; then
    echo "Loading .env file..."
    set -a
    source .env
    set +a
    echo "ANTHROPIC_API_KEY loaded: ${ANTHROPIC_API_KEY:0:20}..."
    echo "OPENAI_API_KEY loaded: ${OPENAI_API_KEY:0:20}..."
fi

# Activate venv if exists, otherwise use system python
if [ -d "aep-venv" ]; then
    source aep-venv/bin/activate
    python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8787
else
    echo "No venv found, using system python3"
    python3 -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8787
fi
