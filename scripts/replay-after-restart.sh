#!/usr/bin/env bash
# E08 evidence: an idempotency key still returns the same order after the API restarts,
# because the key lives in Postgres, not in API memory.
# Usage: scripts/replay-after-restart.sh > docs/evidence/E08-replay-after-restart.txt
#   BASE_URL     default http://localhost:8080
#   RESTART_CMD  default "docker compose restart api api2"; use RESTART_CMD=manual to
#                restart the API yourself (e.g. Ctrl+C and start uvicorn again)
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8080}"
RESTART_CMD="${RESTART_CMD:-docker compose restart api api2}"
KEY="replay-$(date +%s)-$RANDOM"
BODY='{"customer_id":"CUST-REPLAY","items":[{"sku":"PART-200","quantity":1}]}'
post() { curl -s -X POST "$BASE_URL/api/v1/orders" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $KEY" -d "$BODY"; }
stock() { curl -s "$BASE_URL/api/v1/inventory/PART-200"; }

echo "== E08 replay after restart  $(date -u +%FT%TZ)  commit $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
echo "-- stock before: $(stock)"
echo "-- first POST:   $(post)"
echo "-- stock after first POST: $(stock)"

if [ "$RESTART_CMD" = "manual" ]; then
  echo "-- restart the API now, then press Enter" >&2; read -r _
else
  echo "-- restarting: $RESTART_CMD"; $RESTART_CMD
fi
echo "-- waiting for readiness"
until curl -sf "$BASE_URL/health/ready" >/dev/null; do sleep 1; done
echo "-- API ready again at $(date -u +%T)"

echo "-- replay POST (same key, same body): $(post)"
echo "-- stock after replay (must equal 'after first POST'): $(stock)"
