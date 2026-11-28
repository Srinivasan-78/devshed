# shellcheck shell=bash
# Derive the libpq PG* variables from DATABASE_URL so that plain `psql` (in the
# bash scripts) and the Ansible playbooks share one source of truth.

: "${DATABASE_URL:?DATABASE_URL is required}"

eval "$(python3 - <<'PY'
import os
import shlex
from urllib.parse import unquote, urlparse

u = urlparse(os.environ["DATABASE_URL"])
pairs = {
    "PGUSER": unquote(u.username or ""),
    "PGPASSWORD": unquote(u.password or ""),
    "PGHOST": u.hostname or "localhost",
    "PGPORT": str(u.port or 5432),
    "PGDATABASE": (u.path or "/").lstrip("/"),
}
for k, v in pairs.items():
    print(f"export {k}={shlex.quote(v)}")
PY
)"
