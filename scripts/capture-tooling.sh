#!/usr/bin/env bash
# B1 evidence: run on EACH laptop; appends to docs/evidence/E00-tooling.txt
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1
out=docs/evidence/E00-tooling.txt; mkdir -p docs/evidence
{
  echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) · person ${1:-?} ====="
  echo "OS: $(uname -srm)"; [ -f /etc/os-release ] && grep PRETTY_NAME /etc/os-release
  for c in "git --version" "docker version --format {{.Server.Version}}" "docker compose version" \
           "kubectl version --client" "kind version" "python3 --version" "uv --version"; do
    printf '%-45s %s\n' "$c" "$($c 2>&1 | head -1)"
  done
  docker run --rm hello-world >/dev/null 2>&1 && echo "docker run hello-world: OK" || echo "docker run hello-world: FAILED"
  echo
} | tee -a "$out"
