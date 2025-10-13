#!/usr/bin/env bash
# To make this script executable, run: chmod +x scripts/dev_up.sh
set -e
docker compose up -d
echo "Starting Core API (8000) and Realtime API (8001) ..."

python -m backend.api.main &
MAIN_PID=$!
python -m backend.api.realtime &
REALTIME_PID=$!

# Trap signals and kill background processes on exit
trap "echo 'Stopping background processes...'; kill ${MAIN_PID:+$MAIN_PID} ${REALTIME_PID:+$REALTIME_PID} 2>/dev/null || true" SIGINT SIGTERM EXIT

wait $MAIN_PID || true
wait $REALTIME_PID || true
