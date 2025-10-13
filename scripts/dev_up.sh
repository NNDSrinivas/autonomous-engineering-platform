#!/usr/bin/env bash
# To make this script executable, run: chmod +x scripts/dev_up.sh
set -e
docker compose up -d
echo "Starting Core API (8000) and Realtime API (8001) ..."
python -m backend.api.main &
python -m backend.api.realtime &
wait
