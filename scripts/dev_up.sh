#!/usr/bin/env bash
set -e
docker compose up -d
echo "Starting Core API (8000) and Realtime API (8001) ..."
python -m backend.api.main & 
python -m backend.api.realtime &
wait
