# Architecture

FulfillOps accepts orders over HTTP, commits them to Postgres in one transaction, and completes
them asynchronously in background workers. The same container image runs every role. This page
shows how a request travels from the client to a receipt and into the metrics, then where each
piece runs. The reasons behind the design are in [ADR-001](ADR-001.md).

## Components

| Component | Runs as | Responsibility | Code |
| --- | --- | --- | --- |
| API | 2 replicas (`api`, `api2` in Compose; Deployment `fulfillops-api` in Kubernetes) | Validates requests, reserves stock and records the order and its job in one transaction, serves reads, health and `/metrics` | `api/` |
| Worker | 2 replicas (`worker`; Deployment `fulfillops-worker`) | Claims jobs with a lease, completes orders, retries with backoff, dead-letters | `worker/` |
| Migrate | Compose one-shot service; Kubernetes initContainer of the API | Applies `db/migrations/*.sql` once each under an advisory lock | `common/migrate.py` |
| Postgres 16 | `db`; StatefulSet `fulfillops-postgres` + 1 Gi PVC | Single source of truth: catalog, stock, orders, jobs, receipts | `db/migrations/` |
| Redis 7 | `redis`; Deployment `fulfillops-redis` | Deployed but unused: `QUEUE_BACKEND=postgres` (wake-up signal deferred, see ADR-001) | — |

## Data flow: from request to receipt and metrics

```mermaid
flowchart LR
    C[Client] -->|"POST /api/v1/orders<br/>Idempotency-Key"| API

    subgraph API["API (x2)"]
        V["Validate<br/>size, key, JSON, structure,<br/>quantity, SKU"] --> TX
        TX["One transaction<br/>1 claim key (orders)<br/>2 reserve stock (inventory)<br/>3 order_items + jobs row"]
        M["/metrics"]
    end

    TX -->|commit| PG[("Postgres<br/>products · inventory · orders<br/>order_items · jobs · receipts")]
    TX -->|"202 {order_id, queued}"| C

    subgraph W["Worker (x2)"]
        CL["Claim job<br/>FOR UPDATE SKIP LOCKED<br/>20 s lease"] --> P["Process"]
        P -->|success| DONE["Receipt + order completed<br/>+ job done (one tx)"]
        P -->|failure| RT["Retry with backoff<br/>or dead after 5"]
        WM[":9100/metrics"]
    end

    PG -->|"poll every 2 s"| CL
    DONE --> PG
    RT --> PG

    C -->|"GET /api/v1/orders/{id}"| API
    M -->|"business totals read at scrape time"| PG
    PROM[Prometheus scrape] --> M
    PROM --> WM
```

### Order lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant A as API
    participant DB as Postgres
    participant W as Worker

    C->>A: POST /api/v1/orders (Idempotency-Key, body)
    A->>A: validate, aggregate duplicate SKUs, SHA-256 of sorted-key JSON
    A->>DB: BEGIN
    A->>DB: INSERT orders ... ON CONFLICT (idempotency_key) DO NOTHING
    alt key already exists
        DB-->>A: no row
        A->>DB: SELECT order_id, request_hash
        A->>DB: ROLLBACK
        A-->>C: 202 same order_id (same hash) or 409 IDEMPOTENCY_CONFLICT
    else new key
        A->>DB: UPDATE inventory ... WHERE available >= qty (per SKU, sorted)
        A->>DB: INSERT order_items, INSERT jobs (queued)
        A->>DB: COMMIT
        A-->>C: 202 {order_id, status: queued}
    end
    loop every 2 s
        W->>DB: claim oldest runnable job (SKIP LOCKED, lease 20 s)
    end
    W->>DB: order -> processing
    W->>W: process (simulated work)
    alt success
        W->>DB: check I still own the job, INSERT receipt, order completed, job done
    else failure, attempts < 5
        W->>DB: job queued, next_attempt_at = now + backoff
    else failure, attempts = 5
        W->>DB: job dead, order failed (stock stays reserved)
    end
    C->>A: GET /api/v1/orders/{id}
    A-->>C: {status: completed, total_cents}
```

### Order states

```mermaid
stateDiagram-v2
    [*] --> queued: POST accepted (commit)
    queued --> processing: worker claims job
    processing --> completed: receipt written
    processing --> queued: failure, attempts < 5 (backoff)
    processing --> processing: lease expired, another worker reclaims
    processing --> failed: failure, attempts = 5 (job dead)
    completed --> [*]
    failed --> [*]: operator review, stock kept
```

## Where the guarantees live

| Guarantee | Mechanism | Evidence |
| --- | --- | --- |
| No overselling, never negative | `UPDATE ... WHERE available >= qty` + `CHECK (available >= 0)` | E06 |
| One order per key across replicas | `UNIQUE (idempotency_key)` + request hash | E05, E08 |
| Committed order never lost | Order, stock, lines and job in one transaction; 202 after commit | E04, E09 |
| Completed exactly once | Lease + ownership re-check + `receipts` primary key | E09 |
| Bounded retries | `attempts` vs `WORKER_MAX_ATTEMPTS = 5`, then `dead` | E10 |
| Only Ready pods get traffic | `/health/ready` checks the DB and the newest migration | E03, E19, E20 |

## Observability

- **API `/metrics`** (Prometheus text format): `fulfillops_http_requests_total{method,route,status}`
  and the latency histogram `fulfillops_http_request_duration_seconds{method,route}`, counted per
  process; business totals `fulfillops_orders_created_total`, `fulfillops_orders_completed_total`,
  `fulfillops_orders_failed_total`, `fulfillops_worker_retries_total`, read from Postgres at scrape
  time so every replica reports the same value. Labels use the route template, never real IDs.
- **Worker `:9100/metrics`**: `fulfillops_jobs_completed/retried/dead/reclaimed_total{worker}`.
- **Logs**: one JSON object per line on stdout with `ts`, `level`, `service`, `event` and IDs
  (`order_id`, `job_id`, `attempt`, `worker_id`). Never passwords, raw idempotency keys (only an
  8-character hash, `key_fp`), request bodies or exception messages.
- **SLO**: [slo.md](slo.md). Measured p95 24.3 ms over 300 requests on Compose (E21).

## Deployment

### Local: Docker Compose

`db` (healthy) → `migrate` (exits 0) → `api` on :8080, `api2` on :8081, `worker` ×2. Every app
container is read-only with `/tmp` as tmpfs, drops all capabilities and sets `no-new-privileges`.
`compose.fault.yaml` is a drill-only override (8 s processing, poison mode).

### Kubernetes: CI, registry, Git and Argo CD

```mermaid
flowchart LR
    DEV[Developer] -->|pull request| GH[GitHub]
    GH --> CI["CI on every PR<br/>lint · unit-tests<br/>integration-and-contract<br/>build-scan-sbom"]
    CI -->|"merge to main"| PUB["publish<br/>same scanned image"]
    PUB -->|"tag = full commit SHA"| GHCR[(GHCR)]
    DEV -->|"promote PR: newTag = SHA<br/>infra/k8s/kustomization.yaml"| GH
    GH -->|"main, path infra/k8s"| ARGO["Argo CD<br/>auto-sync, prune, self-heal"]
    ARGO --> K8S

    subgraph K8S["kind cluster, namespace fulfillops"]
        SVC["Service fulfillops-api<br/>NodePort 30080 → host 127.0.0.1:8080"] --> APIP["API pods x2<br/>initContainer migrate"]
        WP["Worker pods x2"]
        PGS[("Postgres StatefulSet<br/>PVC, Prune=false")]
        APIP --> PGS
        WP --> PGS
        SEC["Secret fulfillops-db<br/>(script, not in Git)"] -.-> APIP
        SEC -.-> WP
    end
    GHCR -->|pull| APIP
    GHCR -->|pull| WP
```

- **Rollouts**: `RollingUpdate` with `maxSurge: 1`, `maxUnavailable: 0`, `minReadySeconds: 5`,
  `progressDeadlineSeconds: 90`. A new pod receives traffic only once `/health/ready` passes, and an
  old pod is removed only after a new one is available (E19: 961 probes, 0 failures).
- **Recovery**: a bad release is reverted in Git; Argo CD syncs the previous manifest (E20). Manual
  `kubectl` changes are reverted by self-heal (E18).
- **Pod hardening**: non-root UID 10001, read-only root filesystem, all capabilities dropped,
  `allowPrivilegeEscalation: false`, seccomp `RuntimeDefault`, no service-account token mounted,
  CPU and memory requests and limits on every container.
- **Secrets**: `scripts/create-secret.sh` builds Secret `fulfillops-db` from the untracked
  `.env.k8s`; it is never in Git and Argo CD does not manage it.
- **Supply chain**: actions pinned to commit SHAs, Trivy blocks CRITICAL/HIGH with a fix, Syft
  SBOM on every build, immutable SHA tags. Details in [supply-chain.md](supply-chain.md); threats in
  [threat-model.md](threat-model.md).
