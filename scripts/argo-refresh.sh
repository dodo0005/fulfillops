#!/usr/bin/env bash
# Argo polls Git every ~3 min; force an immediate refresh after a merge.
set -euo pipefail
kubectl -n argocd annotate application fulfillops argocd.argoproj.io/refresh=hard --overwrite
kubectl -n argocd get application fulfillops \
  -o jsonpath='{.status.sync.status}{" / "}{.status.health.status}{"  rev="}{.status.sync.revision}{"\n"}'
