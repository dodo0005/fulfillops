#!/usr/bin/env bash
# E09: hard-kill the worker that is processing a committed order; the other worker
# reclaims it after the lease and completes it exactly once.
# Compose (default): start with the drill override first:
#   docker compose -f compose.yaml -f compose.fault.yaml up -d --build --wait
# kind: MODE=kind scripts/fault-kill-worker.sh  (needs WORKER_PROCESSING_DELAY_SECONDS=8 in the ConfigMap via a Git PR)
. "$(dirname "$0")/lib.sh"
out="$EVIDENCE_DIR/E09-worker-crash.log"
{
  evidence_header "MODE=$MODE $0"
  log "STEP 1 create a committed order"
  resp=$(create_order CUST-KILL PART-200 1); echo "$resp"
  [ "${resp%% *}" = 202 ] || { log "expected 202"; exit 1; }
  order_id=$(echo "${resp#* }" | json_get order_id)

  log "STEP 2 wait until a worker is processing it"
  wait_for_status "$order_id" processing 20
  victim=$(psql_q "SELECT locked_by FROM jobs WHERE order_id = '$order_id';")
  psql_q "SELECT status, attempts, locked_by, locked_until FROM jobs WHERE order_id = '$order_id';"
  log "worker holding the job: $victim"

  log "STEP 3 hard kill (SIGKILL, no graceful shutdown)"
  if [ "$MODE" = kind ]; then
    kubectl -n "$NS" delete pod "$victim" --grace-period=0 --force
  else
    for id in $(docker compose ps -q worker); do
      if [ "$(docker inspect -f '{{.Config.Hostname}}' "$id")" = "$victim" ]; then
        docker kill "$id"; log "killed container $id"
      fi
    done
  fi

  log "STEP 4 lease expires, the other worker reclaims and completes"
  wait_for_status "$order_id" completed 90

  log "STEP 5 proof"
  echo "receipts rows (must be 1): $(psql_q "SELECT count(*) FROM receipts WHERE order_id = '$order_id';")"
  echo "job (expect done, attempts=2, other worker):"
  psql_q "SELECT status, attempts, locked_by FROM jobs WHERE order_id = '$order_id';"
  echo "--- job_reclaimed log line"
  if [ "$MODE" = kind ]; then
    kubectl -n "$NS" logs -l app.kubernetes.io/name=fulfillops-worker --tail=-1 | grep job_reclaimed | grep "$order_id" || echo "(none found)"
  else
    docker compose logs --no-color worker | grep job_reclaimed | grep "$order_id" || echo "(none found)"
  fi
} 2>&1 | tee "$out"
[ "$MODE" = compose ] && docker compose up -d worker >/dev/null 2>&1 || true   # restore the killed replica
