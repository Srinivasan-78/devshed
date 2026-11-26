#!/usr/bin/env bash
# Block until Postgres answers, then exec the given command. Used by the worker
# and sweeper services (which must not apply the schema themselves).
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$here/pgenv.sh"

echo "[wait-for-pg] $PGHOST:$PGPORT/$PGDATABASE"
until psql -tAc 'SELECT 1' >/dev/null 2>&1; do
  sleep 1
done
echo "[wait-for-pg] up"

exec "$@"
