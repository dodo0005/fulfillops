#!/usr/bin/env bash
# Gated promotion: open a PR that points infra/k8s at an image `publish` already pushed.
#   scripts/promote.sh <full-40-char-commit-sha>
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
sha="${1:?usage: $0 <full commit sha>}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "need the full 40-char SHA" >&2; exit 1; }
docker manifest inspect "ghcr.io/dodo0005/fulfillops:$sha" >/dev/null \
  || { echo "image not on GHCR (did publish run for this commit?)" >&2; exit 1; }
git switch -c "b/promote-${sha:0:7}" origin/main
sed -i.bak -E "s/^(    newTag: ).*/\1$sha/" infra/k8s/kustomization.yaml && rm infra/k8s/kustomization.yaml.bak
git add infra/k8s/kustomization.yaml
git commit -m "infra(k8s): promote image ${sha:0:7}"
git push -u origin HEAD
echo "Now open the PR (or: gh pr create --fill). After merge: scripts/argo-refresh.sh"
