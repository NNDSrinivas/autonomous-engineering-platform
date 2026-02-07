#!/usr/bin/env sh
set -e

if [ -f /run/secrets/grafana_admin_password ]; then
  export GF_SECURITY_ADMIN_PASSWORD="$(cat /run/secrets/grafana_admin_password)"
fi

if [ -f /run/secrets/grafana_db_password ]; then
  export GF_DATABASE_PASSWORD="$(cat /run/secrets/grafana_db_password)"
fi

if [ -f /run/secrets/navi_db_password ]; then
  export NAVI_DB_PASSWORD="$(cat /run/secrets/navi_db_password)"
fi

exec /run.sh
