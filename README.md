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
TODO

### Person B
TODO: what I implemented, what I reviewed, what I would improve next.
