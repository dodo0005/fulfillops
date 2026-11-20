# FulfillOps

Resilient order-processing platform — EPITA DevOps capstone. Team guide: `docs/team-guide.md`.

## Prerequisites

Git, Docker + Compose v2, kubectl, kind (tested v0.33.0), Python 3.12, uv. Check with `scripts/capture-tooling.sh`.

## Local stack (Docker Compose)

```bash
cp .env.example .env                    # placeholders only; never commit .env
docker compose up -d --build --wait     # db, redis, migrate (runs once), api :8080, api2 :8081, 2 workers
docker compose ps
curl http://localhost:8080/health/ready
docker compose down                     # stops everything, KEEPS the pgdata volume
```

Destroy test data completely: `docker compose down -v`. Reset stock to the seed without deleting the volume (test DB only): `scripts/reset-test-data.sh`.

Public checker on a fresh/reset test stack:

```bash
scripts/reset-test-data.sh
python3 tests/contract/fulfillops_public_checker.py --base-url http://localhost:8080 --concurrency --stress
```

## Kubernetes (kind + Argo CD)

Compose and kind both use host port 8080: `docker compose down` first.

```bash
cp .env.k8s.example .env.k8s            # set a real password in both lines; untracked
scripts/kind-bootstrap.sh               # kind cluster, Argo CD v3.5.6 (pinned), Secret, Argo Application
kubectl -n fulfillops get all,pvc -o wide
curl http://localhost:8080/health/ready # NodePort 30080 -> host 8080, reaches both API pods
```

Teardown: `kind delete cluster --name fulfillops` (the cluster is disposable; this also deletes the lab database).
The test-data reset refuses `APP_ENV=lab`, so run the checker on kind right after a fresh deploy; to rerun, delete the PVC and resync.

Deploy a new version: CI `publish` pushes `ghcr.io/dodo0005/fulfillops:<sha>` → `scripts/promote.sh <sha>` opens a PR → merge → `scripts/argo-refresh.sh`.

## Drills

| Drill | Command | Evidence |
| --- | --- | --- |
| Worker killed mid-job | `docker compose -f compose.yaml -f compose.fault.yaml up -d --build --wait` then `scripts/fault-kill-worker.sh` | `docs/evidence/E09-worker-crash.log` |
| Poison job | `scripts/fault-poison-job.sh` (same override) | `docs/evidence/E10-poison-job.txt` |
| Redis down | set `QUEUE_BACKEND=redis` in `.env`, then `scripts/fault-redis-down.sh` | `docs/evidence/redis-down-drill.txt` |
| Argo CD drift | `scripts/drift-demo.sh` | `docs/evidence/E18-drift.log` |
| Good rollout + 30 s probe | see B9 in the team guide | `docs/rolling_update_probe.csv` |
| Broken rollout + git revert | `scripts/broken-rollout.sh before|during|after` | `docs/evidence/E20-broken-rollout.log` |

## Individual notes

### Person A
### Person A

**What I built.** The application lane: the database schema and migrations (`db/migrations`,
`common/migrate.py`), the API (`api/`) with validation, the error format and the atomic
reservation and idempotency transaction in `api/orders_service.py`, the worker (`worker/`) with
lease-based job claims, retries with exponential backoff, dead-lettering and the poison-job mode,
the `/metrics` endpoint with business totals read from Postgres, and the test-only reset. I wrote
the unit, integration and race tests (`tests/`), the restart-replay and poison-job scripts, the
p95 load script and `docs/slo.md`, and produced evidence E03–E08, E10–E12 and E21. I used an AI
assistant throughout; every use is listed in `docs/assistance-log.md`.

**What I reviewed and fixed in my partner's lane.** I reviewed the Compose, CI and Kubernetes
PRs. Two fixes came out of running my code through the pipeline: the integration job selected
zero tests because of the pytest marker filter (fixed with `-m "integration or race"`), and the
reset step ran outside the containers (now `docker compose exec -T api ...`). When Trivy blocked
the image on CVE-2026-85091 (zlib), I traced it to the Debian base image and added the
`apt-get upgrade` to the runtime stage.

**What I would improve next.** Implement the Redis wake-up signal (deferred: workers poll
Postgres every 2 s), protect `/metrics` instead of exposing it openly, add an operator action to
release stock held by failed orders, measure `POST /orders` latency and not only reads, and add
a Compose healthcheck on the worker's metrics port.

### Person B
TODO: what I implemented, what I reviewed, what I would improve next.
