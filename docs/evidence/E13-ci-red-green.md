# E13 — CI red to green (Trivy quality gate)

## Red: blocked by the vulnerability gate
- Run: https://github.com/dodo0005/fulfillops/actions/runs/44634706829 (commit b863abb)
- build-scan-sbom failed at 'Trivy — BLOCKING (CRITICAL/HIGH with a fix available)'; publish skipped
- Blocking findings:
```
```

## Fix
- Dockerfile: apt-get upgrade in the runtime stage to pull Debian security patches

## Green
- Run: https://github.com/dodo0005/fulfillops/actions/runs/44641559578 (commit 9e14325)
- build-scan-sbom passed; SBOM artifact sbom-9e14325c4e5b757a79ae7256b91491de100f462f
- integration-and-contract still red: worker and /metrics not implemented yet (Person A lane)
