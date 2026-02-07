#!/usr/bin/env bash
set -euo pipefail

GRAFANA_CONTAINER="${GRAFANA_CONTAINER:-grafana}"
PROMETHEUS_CONTAINER="${PROMETHEUS_CONTAINER:-navi-prometheus}"

function remove_container() {
  local name="$1"
  if docker ps -a --format '{{.Names}}' | grep -q "^${name}$"; then
    docker rm -f "${name}" >/dev/null
    echo "Removed ${name}."
  else
    echo "${name} does not exist."
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

remove_container "${GRAFANA_CONTAINER}"
remove_container "${PROMETHEUS_CONTAINER}"
