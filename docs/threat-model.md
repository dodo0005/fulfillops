# Threat model — FulfillOps

Scope: the lab deployment (Docker Compose for local tests, kind + Argo CD for Kubernetes, GitHub Actions for CI/CD, GHCR for images). Each threat lists what could go wrong, how we mitigate it, and where the mitigation lives.

| # | Threat | Mitigation | Where |
|---|---|---|---|
| T1 | **Oversized request body** used to exhaust API memory | Body limited to 16 KiB; larger bodies rejected with 413 before parsing | `MAX_BODY_BYTES`, API middleware (`api/middleware.py`) |
| T2 | **Injection** through SKU, customer ID or order ID | Parameterized SQL only (psycopg placeholders, no string-built queries); order IDs validated as UUIDs, invalid ones return 404 | `api/`, `worker/` SQL code |
| T3 | **Overselling under concurrent orders** (race condition) | Conditional `UPDATE inventory ... WHERE available >= qty` inside one transaction; `CHECK (available >= 0)` in the schema | `db/migrations/001_init.sql`, order service |
| T4 | **Idempotency-key replay or reuse** with a different payload | `UNIQUE (idempotency_key)` + SHA-256 hash of the canonical request; same key with a different payload → 409 `IDEMPOTENCY_CONFLICT` | schema + order service |
| T5 | **Poison message** looping forever and starving workers | Bounded retries (`WORKER_MAX_ATTEMPTS=5`) with capped exponential backoff, then `dead` job / `failed` order for manual review | worker processor, E10 evidence |
| T6 | **Secrets leaked** into Git, logs or CI output | `.env` and `.env.k8s` ignored by Git, only placeholder `.env.example` files committed; Kubernetes Secret created from an untracked file by `scripts/create-secret.sh` and not managed by Argo CD; DB URL excluded from config `repr`; CI uses only the built-in `GITHUB_TOKEN`; GitGuardian scan on every PR | `.gitignore`, `scripts/create-secret.sh`, `common/config.py`, `.github/workflows/ci.yaml` |
| T7 | **Compromised dependency or GitHub Action** (supply chain) | All actions pinned to full commit SHAs (a tag can be moved to malicious code, as happened to `trivy-action` tags in March 2026); dependencies locked in `uv.lock` and installed with `--frozen`; Syft SBOM published for every build | `.github/workflows/ci.yaml`, `uv.lock`, `docs/supply-chain.md` |
| T8 | **Known vulnerability in the image** | Trivy blocks the PR on CRITICAL/HIGH with a fix available; all other findings reported as informational; base image pinned to an exact patch tag and Debian security patches applied at build | `build-scan-sbom` job, `Dockerfile`, E13 evidence |
| T9 | **Container breakout / privilege escalation** after a compromise | Non-root user (UID 10001), read-only root filesystem, all Linux capabilities dropped, `no-new-privileges` / `allowPrivilegeEscalation: false`, seccomp `RuntimeDefault`, no service-account token mounted | `Dockerfile`, `compose.yaml`, `infra/k8s/*.yaml` |
| T10 | **Unreviewed or manual change** reaching the cluster | All changes go through a PR and CI; Argo CD deploys only what is on `main` and self-heal reverts manual drift; Postgres marked `Prune=false` so it is never deleted automatically | `infra/argocd/application.yaml`, `infra/k8s/postgres.yaml`, E18 evidence |
| T11 | **Bad release taking the service down** | Rolling update with `maxUnavailable: 0`, readiness probe, `progressDeadlineSeconds: 90`; recovery through `git revert` | `infra/k8s/api.yaml`, E19 / E20 evidence |
| T12 | **Exposed internal endpoints** (`/metrics`, database, Redis, Argo CD UI) | Postgres and Redis are ClusterIP only (not reachable from outside the cluster); the API NodePort is bound to `127.0.0.1` on the lab host; Argo CD UI only through a local port-forward | `infra/k8s/*.yaml`, `infra/kind-config.yaml` |

## Known limitations (lab vs production)

- **Secrets:** created by hand from an untracked file. In production we would use Sealed Secrets or External Secrets Operator so secrets can be managed through GitOps without being readable in Git.
- **Network:** no NetworkPolicies yet; in production, only the API should be able to reach Postgres and Redis, and `/metrics` should only be reachable by the monitoring system.
- **Authentication:** the API has no authentication or rate limiting; a real deployment would put it behind an authenticated gateway.
- **Image trust:** images are tagged by commit SHA and scanned, but not signed; production would add image signing (e.g. cosign) and verify signatures before deploy.
- **Branch protection:** CI runs on every PR, but merging is only fully blocked by a red check once the checks are marked as *required* in the repository settings.
