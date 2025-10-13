#!/usr/bin/env bash
set -e
until pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-mentor}" >/dev/null 2>&1; do
  echo "Waiting for Postgres..."
  sleep 2
done
echo "Postgres is ready."
