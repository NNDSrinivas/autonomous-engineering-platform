#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAFANA_PORT="${GRAFANA_PORT:-3001}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
GRAFANA_CONTAINER="${GRAFANA_CONTAINER:-grafana}"
PROMETHEUS_CONTAINER="${PROMETHEUS_CONTAINER:-navi-prometheus}"

cd "$ROOT_DIR"

function ensure_docker_running() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required but not installed."
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop and retry."
    exit 1
  fi
}

function start_prometheus() {
  if docker ps --format '{{.Names}}' | grep -q "^${PROMETHEUS_CONTAINER}$"; then
    echo "Prometheus already running (${PROMETHEUS_CONTAINER})."
    return
  fi

  if docker ps -a --format '{{.Names}}' | grep -q "^${PROMETHEUS_CONTAINER}$"; then
    docker start "${PROMETHEUS_CONTAINER}" >/dev/null
    echo "Prometheus container started (${PROMETHEUS_CONTAINER})."
    return
  fi

  if [ ! -f "$ROOT_DIR/prometheus/prometheus.yml" ]; then
    echo "Missing prometheus/prometheus.yml."
    exit 1
  fi

  docker run -d \
    -p "${PROMETHEUS_PORT}:9090" \
    --name "${PROMETHEUS_CONTAINER}" \
    -v "$ROOT_DIR/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml" \
    -v "$ROOT_DIR/prometheus/alerts:/etc/prometheus/alerts" \
    prom/prometheus:latest >/dev/null

  echo "Prometheus started on http://localhost:${PROMETHEUS_PORT}."
}

function start_grafana() {
  if docker ps --format '{{.Names}}' | grep -q "^${GRAFANA_CONTAINER}$"; then
    echo "Grafana already running (${GRAFANA_CONTAINER})."
    return
  fi

  if docker ps -a --format '{{.Names}}' | grep -q "^${GRAFANA_CONTAINER}$"; then
    docker start "${GRAFANA_CONTAINER}" >/dev/null
    echo "Grafana container started (${GRAFANA_CONTAINER})."
    return
  fi

  docker run -d \
    -p "${GRAFANA_PORT}:3000" \
    --name "${GRAFANA_CONTAINER}" \
    -v "$ROOT_DIR/grafana/provisioning:/etc/grafana/provisioning" \
    -v "$ROOT_DIR/grafana/dashboards:/var/lib/grafana/dashboards" \
    grafana/grafana >/dev/null

  echo "Grafana started on http://localhost:${GRAFANA_PORT}."
}

function wait_for_grafana() {
  local base_url="http://localhost:${GRAFANA_PORT}"
  echo "Waiting for Grafana API..."
  for _ in {1..30}; do
    if curl -fs "${base_url}/api/health" >/dev/null 2>&1; then
      echo "Grafana API is healthy."
      return
    fi
    sleep 1
  done
  echo "Grafana did not become healthy in time."
  exit 1
}

function verify_dashboards() {
  local base_url="http://admin:admin@localhost:${GRAFANA_PORT}"
  local result
  result=$(curl -fs "${base_url}/api/search?type=dash-db" | tr -d '\n')

  echo "Verifying dashboards are loaded..."
  for uid in navi-llm-metrics navi-task-metrics navi-errors navi-learning; do
    if ! echo "$result" | grep -q "\"uid\":\"${uid}\""; then
      echo "Missing dashboard uid: ${uid}"
      exit 1
    fi
  done

  echo "All dashboards are present."
}

ensure_docker_running
start_prometheus
start_grafana
wait_for_grafana
verify_dashboards

cat <<EOF_SUMMARY

Success.
- Grafana: http://localhost:${GRAFANA_PORT} (admin/admin)
- Prometheus: http://localhost:${PROMETHEUS_PORT}
Dashboards loaded: navi-llm-metrics, navi-task-metrics, navi-errors, navi-learning
EOF_SUMMARY
