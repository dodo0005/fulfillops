#!/usr/bin/env bash
# E20: capture cluster state at each phase of the broken-rollout drill.
#   scripts/broken-rollout.sh before   (before merging the "break readiness" PR)
#   scripts/broken-rollout.sh during   (after merge + argo-refresh, wait ~100 s)
#   scripts/broken-rollout.sh after    (after merging the git revert PR)
. "$(dirname "$0")/lib.sh"
MODE=kind
phase="${1:?usage: $0 before|during|after}"
out="$EVIDENCE_DIR/E20-broken-rollout.log"
{
  echo "=================== PHASE: $phase ==================="
  evidence_header "$0 $phase"
  git fetch -q origin main && echo "origin/main: $(git rev-parse origin/main)  $(git log -1 --format=%s origin/main)"
  echo "--- argo"
  kubectl -n argocd get application fulfillops \
    -o jsonpath='{.status.sync.status}{" / "}{.status.health.status}{"  rev="}{.status.sync.revision}{"\n"}'
  echo "--- rollout status (5 s timeout)"
  kubectl -n "$NS" rollout status deploy/fulfillops-api --timeout=5s || true
  echo "--- deployment conditions"
  kubectl -n "$NS" get deploy fulfillops-api \
    -o jsonpath='{range .status.conditions[*]}{.type}{"="}{.status}{"  "}{.reason}{"  "}{.message}{"\n"}{end}'
  echo "--- replicasets / pods"
  kubectl -n "$NS" get rs,pods -l app.kubernetes.io/name=fulfillops-api -o wide
  echo "--- rollout history"
  kubectl -n "$NS" rollout history deploy/fulfillops-api
  echo "--- recent events"
  kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -20
  echo "--- committed orders (must not drop)"
  psql_q "SELECT status, count(*) FROM orders GROUP BY status ORDER BY status;"
  echo "--- user view"
  curl -s -o /dev/null -w "GET /health/ready -> %{http_code}\n" "$BASE_URL/health/ready"
  echo
} 2>&1 | tee -a "$out"
