#!/usr/bin/env bash
# Redis-down drill (Compose, QUEUE_BACKEND=redis in .env): the API keeps accepting
# orders and the Postgres sweeper still completes them. Postgres is the truth.
. "$(dirname "$0")/lib.sh"
out="$EVIDENCE_DIR/redis-down-drill.txt"
{
  evidence_header "$0"
  log "QUEUE_BACKEND in api: $(docker compose exec -T api printenv QUEUE_BACKEND)"
  log "STOP redis"; docker compose stop redis
  ids=()
  for i in 1 2 3; do
    resp=$(create_order "CUST-REDIS-$i" PART-200 1); echo "$resp"
    ids+=("$(echo "${resp#* }" | json_get order_id)")
  done
  for id in "${ids[@]}"; do wait_for_status "$id" completed 60; done
  log "START redis"; docker compose start redis
  docker compose ps
} 2>&1 | tee "$out"
