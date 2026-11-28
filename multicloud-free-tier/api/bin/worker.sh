#!/usr/bin/env bash
# Polls Postgres for work and hands each job to Ansible.
#
# One row at a time, claimed atomically with FOR UPDATE SKIP LOCKED and a
# claimed_at stamp, so running two workers never double-runs a job.
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$here/pgenv.sh"
cd "$here/.." || exit 1

export ANSIBLE_RETRY_FILES_ENABLED=0
export ANSIBLE_LOCALHOST_WARNING=0
export ANSIBLE_INVENTORY_UNPARSED_WARNING=0
export PYTHONPATH="$here/.."

claim_sql="
UPDATE resources SET claimed_at = now()
WHERE id = (
    SELECT id FROM resources
    WHERE (claimed_at IS NULL OR claimed_at < now() - interval '30 minutes')
      AND status IN ('pending', 'destroying')
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id::text || ' ' || status;
"

echo "[worker] started"
while true; do
  job="$(psql -XqtAc "$claim_sql" 2>/dev/null || true)"
  if [ -z "$job" ]; then
    sleep 3
    continue
  fi

  id="${job%% *}"
  status="${job##* }"
  case "$status" in
    pending)    playbook=provision.yml ;;
    destroying) playbook=destroy.yml ;;
    *)          echo "[worker] unexpected status '$status' for $id"; continue ;;
  esac

  echo "[worker] $status $id -> ansible-playbook $playbook"
  if ansible-playbook -i 'localhost,' -c local "ansible/$playbook" -e "resource_id=$id"; then
    echo "[worker] done $id"
  else
    echo "[worker] FAILED $id"
    psql -Xq -v id="$id" <<'SQL' || true
UPDATE resources
   SET status = 'error',
       error_message = 'worker: ansible-playbook run failed',
       claimed_at = NULL,
       updated_at = now()
 WHERE id = :'id';
SQL
  fi
done
