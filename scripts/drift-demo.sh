#!/usr/bin/env bash
# E18: manual drift (kubectl scale to 5) is detected and reverted by Argo CD self-heal.
. "$(dirname "$0")/lib.sh"
out="$EVIDENCE_DIR/E18-drift.log"
status() {
  printf '[%s] argo=%s/%s  spec.replicas=%s  ready=%s\n' "$(ts)" \
    "$(kubectl -n argocd get application fulfillops -o jsonpath='{.status.sync.status}')" \
    "$(kubectl -n argocd get application fulfillops -o jsonpath='{.status.health.status}')" \
    "$(kubectl -n $NS get deploy fulfillops-api -o jsonpath='{.spec.replicas}')" \
    "$(kubectl -n $NS get deploy fulfillops-api -o jsonpath='{.status.readyReplicas}')"
}
{
  evidence_header "$0"
  log "BEFORE"; status
  log "DRIFT: kubectl -n $NS scale deploy/fulfillops-api --replicas=5"
  kubectl -n "$NS" scale deploy/fulfillops-api --replicas=5
  for _ in $(seq 1 36); do   # up to 3 minutes
    sleep 5; status
    [ "$(kubectl -n $NS get deploy fulfillops-api -o jsonpath='{.spec.replicas}')" = 2 ] && { log "REVERTED to 2 by Argo CD"; break; }
  done
  log "AFTER"; status
  kubectl -n argocd get application fulfillops -o jsonpath='{range .status.history[-3:]}{.id}{" "}{.revision}{" "}{.deployedAt}{"\n"}{end}'
} 2>&1 | tee "$out"
