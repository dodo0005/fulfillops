# Assistance log

Every use of AI or external code, as required by section 7 of the assignment.

| Date | Person | What it produced | Files |
| --- | --- | --- | --- 
| 2026-11-10 | Person A | Project skeleton: pyproject, config loader, JSON logging, config unit tests | `pyproject.toml`, `common/config.py`, `common/logging.py`, `tests/unit/test_config.py` |
| 2026-11-10 | Person B | Claude: first draft of Dockerfile, Dockerfile.naive, .dockerignore, compose.yaml, compose.fault.yaml, .env examples, PR template, setup scripts. Tested locally: stack healthy, non-root uid 10001 | `Dockerfile*`, `.dockerignore`, `compose*.yaml`, `.env*.example`, `.github/pull_request_template.md`, `scripts/capture-tooling.sh`, `scripts/reset-test-data.sh` |
| 2026-11-11 | Person B | Claude: draft of CI workflow (lint, unit, integration+checker, Trivy gate, Syft SBOM, GHCR publish) and supply-chain policy | `.github/workflows/ci.yaml`, `docs/supply-chain.md` |
