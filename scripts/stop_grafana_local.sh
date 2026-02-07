#!/usr/bin/env bash
set -euo pipefail

GRAFANA_CONTAINER="${GRAFANA_CONTAINER:-grafana}"
PROMETHEUS_CONTAINER="${PROMETHEUS_CONTAINER:-navi-prometheus}"

function stop_container() {
  local name="$1"
  if docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
    docker stop "${name}" >/dev/null
    echo "Stopped ${name}."
  else
    echo "${name} is not running."
  fi
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required but not installed."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and retry."
  exit 1
fi

stop_container "${GRAFANA_CONTAINER}"
stop_container "${PROMETHEUS_CONTAINER}"
