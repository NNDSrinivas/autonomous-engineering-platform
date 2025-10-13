#!/usr/bin/env bash
# To make this script executable, run: chmod +x scripts/dev_down.sh
set -e
docker compose down -v
pkill -f "backend.api.main" || true
pkill -f "backend.api.realtime" || true
