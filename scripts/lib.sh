# shellcheck shell=bash
# Shared helpers for FulfillOps scripts. Source it: . "$(dirname "$0")/lib.sh"
# MODE=compose (default) or MODE=kind selects where psql runs.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

MODE="${MODE:-compose}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
NS=fulfillops
EVIDENCE_DIR=docs/evidence
mkdir -p "$EVIDENCE_DIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log() { echo "[$(ts)] $*"; }

# Header required on every evidence file: date, commit, exact command.
evidence_header() {
  echo "# date:    $(ts)"
  echo "# commit:  $(git rev-parse HEAD)"
  echo "# command: $*"
  echo "# mode:    $MODE"
  echo
}

psql_q() {  # psql_q "SQL" -> unaligned, tuples only
  if [ "$MODE" = kind ]; then
    kubectl -n "$NS" exec -i statefulset/fulfillops-postgres -- \
      psql -U fulfillops -d fulfillops -v ON_ERROR_STOP=1 -tAc "$1"
  else
    docker compose exec -T db sh -c 'psql -U fulfillops -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -tAc "$0"' "$1"
  fi
}

json_get() {  # echo '{"a":1}' | json_get a
  python3 -c 'import json,sys; print(json.load(sys.stdin).get(sys.argv[1], ""))' "$1"
}

create_order() {  # create_order <customer_id> <sku> <qty>  -> prints "<http_code> <body>"
  local key
  key="drill-$(date +%s)-$RANDOM-$RANDOM"
  curl -sS -o /tmp/fo_body.json -w '%{http_code}' -X POST "$BASE_URL/api/v1/orders" \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $key" \
    -d "{\"customer_id\":\"$1\",\"items\":[{\"sku\":\"$2\",\"quantity\":$3}]}"
  echo " $(cat /tmp/fo_body.json)"
}

order_status() { curl -sS "$BASE_URL/api/v1/orders/$1" | json_get status; }

wait_for_status() {  # wait_for_status <order_id> <status> <timeout_s>
  local deadline=$(( $(date +%s) + $3 )) s
  while [ "$(date +%s)" -lt "$deadline" ]; do
    s=$(order_status "$1")
    [ "$s" = "$2" ] && { log "order $1 is $s"; return 0; }
    sleep 0.5
  done
  log "TIMEOUT: order $1 never reached $2 (last: ${s:-?})"; return 1
}
