#!/bin/bash
# Start backend with dev environment variables

export DEV_USER_ID="dev-user-1"
export DEV_USER_EMAIL="srinivasn7779@gmail.com"
export DEV_ORG_ID="default-org"
export DEV_USER_ROLE="admin"

cd /Users/mounikakapa/Desktop/Personal\ Projects/autonomous-engineering-platform

# Activate venv
source aep-venv/bin/activate

# Start backend
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8787
