#!/usr/bin/env bash
# Creates Secret fulfillops-db from the UNTRACKED file .env.k8s (see .env.k8s.example).
# The Secret is never in Git and Argo CD does not manage it.
# Production answer: Sealed Secrets or External Secrets Operator (see docs/threat-model.md).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -f .env.k8s ] || { echo "missing .env.k8s — cp .env.k8s.example .env.k8s and set a password" >&2; exit 1; }
grep -q change-me .env.k8s && { echo "refusing: .env.k8s still contains the placeholder 'change-me'" >&2; exit 1; }
kubectl create namespace fulfillops --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic fulfillops-db --from-env-file=.env.k8s -n fulfillops \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n fulfillops get secret fulfillops-db   # shows keys count only, never values
