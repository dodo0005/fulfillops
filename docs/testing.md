# Testing

Every invariant from the assignment, the test that proves it, and how to run it.
Unit tests need nothing; integration and race tests need a running API + worker on the
isolated test database (`bash scripts/reset-test-data.sh` first, they consume stock).

## How to run

| Layer | Command | Runs in CI job |
| --- | --- | --- |
| Unit | `uv run pytest -q` | `unit-tests` |
| Integration | `uv run pytest -m integration -v` | `integration-and-contract` |
| Race | `FULFILLOPS_URLS=http://localhost:8080,http://localhost:8081 uv run pytest -m race -v` | `integration-and-contract` |
| Contract | `python3 tests/contract/fulfillops_public_checker.py --concurrency --stress` | `integration-and-contract` (must be 15/0/0) |
| Fault drills | `scripts/fault-kill-worker.sh`, `scripts/fault-poison-job.sh`, `scripts/replay-after-restart.sh` | manual, evidence in `docs/evidence/` |

## Test matrix

| Layer | File | What it proves | Evidence |
| --- | --- | --- | --- |
| Unit | `tests/unit/test_config.py` | Config fails fast on missing/invalid values; the DB password never appears in `repr` or logs | CI `unit-tests` |
| Unit | `tests/unit/test_migrate.py` | Migrations are found and applied in order; readiness checks the newest one | CI `unit-tests` |
| Unit | `tests/unit/test_errors.py` | Every error uses `{"error":{"code","message"}}`; unexpected errors leak no SQL or secrets | CI `unit-tests` |
| Unit | `tests/unit/test_validation.py` | Validation order; bool/float/0/21 quantities rejected; key length and charset; duplicate lines aggregated and sorted; hash ignores key order | CI `unit-tests`, E12 |
| Unit | `tests/unit/test_body_limit.py` | Bodies over 16 KiB refused with 413, including chunked bodies without Content-Length | CI `unit-tests` |
| Unit | `tests/unit/test_reset_guard.py` | Reset refuses anything but `APP_ENV=test` with a `*test*` database | CI `unit-tests`, E04 header |
| Unit | `tests/unit/test_processor.py` | Backoff doubles, is capped and jittered; poison mode only when explicitly enabled | CI `unit-tests` |
| Unit | `tests/unit/test_metrics.py` | Metric labels use route templates (no IDs); business totals read from Postgres; DB outage does not break `/metrics` | CI `unit-tests` |
| Integration | `tests/integration/test_read_routes.py` | Catalog prices, inventory reading, 404 for unknown SKU and order (incl. non-UUID IDs) | CI |
| Integration | `tests/integration/test_order_validation.py` | Each validation error code through the real API; nothing is created | CI |
| Integration | `tests/integration/test_orders.py` | Create + replay reserves once; same key + other payload = 409; out-of-stock changes nothing; failure on line 2 rolls back line 1 | CI |
| Integration | `tests/integration/test_idempotency_key_order.py` | Reordered JSON keys count as the same request (the E12 red-to-green test) | E12 |
| Integration | `tests/integration/test_worker.py` | Worker completes an order with the correct total | CI |
| Integration | `tests/integration/test_multiline.py` | 2+2 PACK-300 reserves 4 and bills 996 cents | E07 |
| Integration | `tests/integration/test_metrics_endpoint.py` | `/metrics` exposes all required series, no customer IDs | CI, E21 |
| Race | `tests/race/test_distinct_key_race.py` | N+5 simultaneous buyers for N units: exactly N accepted, 5 OUT_OF_STOCK, stock 0, never negative | E06 |
| Race | `tests/race/test_same_key_cross_replica.py` | 8 identical requests over 2 API replicas: one order, stock -1 (hard gate 1) | E05 |
| Contract | `tests/contract/fulfillops_public_checker.py` | Instructor's black-box checks, unchanged | E04 |
| Drill | `scripts/replay-after-restart.sh` | Idempotency survives an API restart | E08 |
| Drill | `scripts/fault-poison-job.sh` | Bounded retries with growing delay, then dead-letter; stock stays reserved (hard gate 2) | E10 |
| Drill | `scripts/fault-kill-worker.sh` (Person B) | Worker killed mid-job: lease expires, job reclaimed, completed exactly once (hard gate 2) | E09 |
| Load | `scripts/load-p95.py` | p50/p95/p99 from 300 raw samples | E21 |



## Deliberate bug caught by tests (E12)

**Bug:** `canonical_hash` serialized the request without `sort_keys=True`, so the same order
with JSON keys in a different order produced a different hash. A client retrying its own
order would be told `409 IDEMPOTENCY_CONFLICT`.

**Caught by:** `tests/unit/test_validation.py::test_hash_ignores_key_order` and
`tests/integration/test_idempotency_key_order.py::test_reordered_json_keys_replay_same_order`.

- Red CI run: https://github.com/dodo0005/fulfillops/actions/runs/44765612297/job/136389297044?pr=14
- Green CI run (fix restored): https://github.com/dodo0005/fulfillops/actions/runs/44767761265/job/136396879808?pr=14
- Local output: `docs/evidence/E12-bug-red.txt`, `docs/evidence/E12-bug-green.txt`