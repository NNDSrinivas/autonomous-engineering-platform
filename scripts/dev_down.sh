#!/usr/bin/env bash
set -e
docker compose down -v
pkill -f "backend.api.main" || true
pkill -f "backend.api.realtime" || true
