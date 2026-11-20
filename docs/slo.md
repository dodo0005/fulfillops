# Service level objectives (lab)

## SLIs and targets

| SLI | Measured from | Target (lab) |
| --- | --- | --- |
| Availability: share of API requests that are not 5xx | `fulfillops_http_requests_total` by `status` | 99.5 % over the test window |
| Latency: p95 of read requests (catalog, inventory) | `scripts/load-p95.py` raw samples (nearest-rank), cross-checked with `fulfillops_http_request_duration_seconds` | p95 < 300 ms |
| Order completion: accepted orders completed by a worker | `fulfillops_orders_completed_total` / `fulfillops_orders_created_total` | 99 % within 15 s, excluding deliberate poison orders |
| Correctness: inventory never negative, one order per idempotency key | DB constraints + race tests (E05, E06) | 0 violations (hard invariant, not a percentage) |

## Measured result

Fill in from `docs/evidence/E21-p95.txt`:

- Date / commit:
- Samples: (at least 200) — errors:
- p50: — p95: — p99:
- Verdict: within / outside target

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
