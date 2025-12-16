#!/usr/bin/env bash
# Simple test script to run the container with minimal environment

echo "Testing AEP backend Docker container..."
echo "Building image..."

docker build -t aep-backend . || exit 1

echo "Starting container with minimal environment..."

# Run with basic environment - no OpenAI key for testing
docker run --rm -p 8787:8787 \
  -e APP_ENV=development \
  -e BACKEND_PUBLIC_URL=http://localhost:8787 \
  -e DATABASE_URL=sqlite:///app/data/test.db \
  aep-backend &

# Wait a moment for startup
sleep 3

echo "Testing health endpoint..."
curl -f http://localhost:8787/health || echo "Health check failed"

echo "Testing info endpoint..."
curl -f http://localhost:8787/api/internal/info || echo "Info endpoint failed"

# Stop the container
docker stop $(docker ps -q --filter ancestor=aep-backend) 2>/dev/null

echo "Test completed."