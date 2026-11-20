# Service level objectives (lab)

## SLIs and targets

| SLI | Measured from | Target (lab) |
| --- | --- | --- |
| Availability: share of API requests that are not 5xx | `fulfillops_http_requests_total` by `status` | 99.5 % over the test window |
| Latency: p95 of read requests (catalog, inventory) | `scripts/load-p95.py` raw samples (nearest-rank), cross-checked with `fulfillops_http_request_duration_seconds` | p95 < 300 ms |
| Order completion: accepted orders completed by a worker | `fulfillops_orders_completed_total` / `fulfillops_orders_created_total` | 99 % within 15 s, excluding deliberate poison orders |
| Correctness: inventory never negative, one order per idempotency key | DB constraints + race tests (E05, E06) | 0 violations (hard invariant, not a percentage) |

## Measured result

Measured on 2026-11-20, commit 06d14c6, fresh Docker Compose stack (API + worker + Postgres on one laptop),
with `scripts/load-p95.py` against `http://localhost:8080`. Raw samples: `docs/evidence/E21-p95-samples.csv`.

| Samples | Errors | p50 | p95 | p99 | Max |
| --- | --- | --- | --- | --- | --- |
| 300 | 0 (0.00 %) | 5.9 ms | 24.3 ms | 26.0 ms | 49.8 ms |

**Verdict: within target.** p95 is 24.3 ms against a 300 ms objective, and availability was 100 % (0 of 300
requests failed, target 99.5 %). The margin is large because the test is read-only and local (see the
limitations below); a real deployment would need its own measurement before relying on this SLO.
## How to reproduce

```bash
python3 scripts/load-p95.py --base-url http://localhost:8080 --samples 300 \
  --output docs/evidence/E21-p95-samples.csv | tee docs/evidence/E21-p95.txt
curl -s localhost:8080/metrics | grep fulfillops_ >> docs/evidence/E21-p95.txt
```

## Limitations of these numbers

- One laptop: the load generator, API, worker and Postgres share the same CPU, so latency
  includes contention that a real deployment would not have.
- No real network: requests go through localhost (or the kind NodePort), so network latency
  and TLS cost are missing.
- Sequential client: one request at a time measures latency, not maximum throughput.
- Small sample (hundreds of requests, minutes): enough to estimate p95, too short to show
  slow drifts, garbage-collection pauses or daily patterns. p99 from 300 samples rests on
  only 3 data points.
- Read-only traffic: POST /orders latency (one transaction with row locks) is not included,
  because generating orders would consume the fixed test stock.
- kind adds an extra hop (NodePort and kube-proxy); numbers from Compose and kind are not
  directly comparable.
