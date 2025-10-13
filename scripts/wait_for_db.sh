#!/usr/bin/env bash
# To make this script executable, run: chmod +x scripts/wait_for_db.sh
set -e

# Check if pg_isready is available
if ! command -v pg_isready >/dev/null 2>&1; then
  echo "Error: pg_isready command not found. Please install PostgreSQL client tools." >&2
  exit 1
fi

until pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-mentor}" >/dev/null 2>&1; do
  echo "Waiting for Postgres..."
  sleep 2
done
echo "Postgres is ready."
