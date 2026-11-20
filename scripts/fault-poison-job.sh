#!/usr/bin/env bash
# E10 evidence: a poison order is retried with growing delays, then dead-lettered.
# Needs a worker running with POISON_TEST_MODE=true (never in production).
# Usage: scripts/fault-poison-job.sh > docs/evidence/E10-poison-job.txt
#   BASE_URL     API address               (default http://localhost:8080)
#   PSQL         command that runs psql     (default: docker exec pg psql -U fulfillops -d fulfillops_test)
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8080}"
PSQL="${PSQL:-docker exec -i pg psql -U fulfillops -d fulfillops_test}"
sql() { $PSQL -At -c "$1"; }

echo "== E10 poison job drill  $(date -u +%FT%TZ)  commit $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
echo "-- inventory before"; sql "SELECT sku, available FROM inventory ORDER BY sku"

KEY="poison-$(date +%s)-$RANDOM"
RESP=$(curl -s -X POST "$BASE_URL/api/v1/orders" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $KEY" \
  -d '{"customer_id":"POISON-TEST","items":[{"sku":"PACK-300","quantity":1}]}')
echo "-- POST response: $RESP"
ORDER_ID=$(echo "$RESP" | sed -n 's/.*"order_id":"\([^"]*\)".*/\1/p')
[ -n "$ORDER_ID" ] || { echo "no order_id, stopping"; exit 1; }

echo "-- polling order status (max 120 s)"
for _ in $(seq 1 120); do
  STATUS=$(curl -s "$BASE_URL/api/v1/orders/$ORDER_ID" | sed -n 's/.*"status":"\([^"]*\)".*/\1/p')
  echo "$(date -u +%T) status=$STATUS"
  [ "$STATUS" = "failed" ] && break
  sleep 1
done

echo "-- job row (dead-letter state)"
sql "SELECT status, attempts, max_attempts, last_error FROM jobs WHERE order_id = '$ORDER_ID'"
echo "-- waiting 60 s to prove there are no more retries"; sleep 60
sql "SELECT status, attempts FROM jobs WHERE order_id = '$ORDER_ID'"
echo "-- inventory after (PACK-300 stays reserved: no automatic restock)"
sql "SELECT sku, available FROM inventory ORDER BY sku"
echo "-- operator review query"
sql "SELECT order_id, attempts, last_error FROM jobs WHERE status = 'dead'"
