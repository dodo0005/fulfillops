#!/usr/bin/env bash
# kind cluster + Argo CD (pinned) + Secret + Argo Application.
# Stop the Compose stack first: both use host port 8080.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
ARGOCD_VERSION="${ARGOCD_VERSION:-v3.5.6}"   # pinned; recorded in README

if ! kind get clusters | grep -qx fulfillops; then
  kind create cluster --name fulfillops --config infra/kind-config.yaml --wait 120s
fi
kubectl cluster-info --context kind-fulfillops

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=300s
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
kubectl -n argocd get deploy,sts,pods

./scripts/create-secret.sh
kubectl apply -f infra/argocd/application.yaml
echo
echo "Argo CD UI:  kubectl -n argocd port-forward svc/argocd-server 8443:443  ->  https://localhost:8443 (user admin)"
echo "Password (do NOT screenshot or paste anywhere):"
echo "  kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
