#!/usr/bin/env bash
set -euo pipefail

APP_NAME="aep-backend"
IMAGE_NAME="navralabs/aep-backend:latest"
CONTAINER_PORT=8787      # inside container
HOST_PORT=8000          # exposed on EC2

echo ">>> [1/4] Pulling latest code from main..."
git fetch --all
git checkout main
git pull origin main

echo ">>> [2/4] Building Docker image..."
docker build -f Dockerfile -t "$IMAGE_NAME" .

echo ">>> [3/4] Stopping existing container (if any)..."
docker stop "$APP_NAME" 2>/dev/null || true
docker rm "$APP_NAME" 2>/dev/null || true

echo ">>> [4/4] Starting new container..."
docker run -d --name "$APP_NAME" \
  --restart=always \
  --env-file .env \
  -p ${HOST_PORT}:${CONTAINER_PORT} \
  "$IMAGE_NAME"

echo ">>> Deployment complete."
docker ps --filter "name=$APP_NAME"

echo ""
echo ">>> Testing health endpoints..."
sleep 3
echo "Live check:"
curl -s http://127.0.0.1:${HOST_PORT}/health/live | head -n 5 || echo "Failed"
echo ""
echo "Ready check:"
curl -s http://127.0.0.1:${HOST_PORT}/health/ready | head -n 5 || echo "Failed (expected if DB/Redis not configured)"