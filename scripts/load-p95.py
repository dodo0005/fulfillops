#!/usr/bin/env python3
"""E21: measure request latency and report p50 / p95 / p99 from raw samples.

Standard library only. Read-only traffic (catalog, inventory, order lookup), so it never
consumes stock and is safe to run at any time against the test stack.

Usage:
  python3 scripts/load-p95.py --base-url http://localhost:8080 --samples 300 \
      --output docs/evidence/E21-p95-samples.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

PATHS = [
    "/api/v1/catalog",
    "/api/v1/inventory/KIT-100",
    "/api/v1/inventory/PART-200",
    "/api/v1/inventory/PACK-300",
]


def percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest value with at least pct % of samples <= it."""
    if not sorted_values:
        raise ValueError("no samples")
    rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def timed_get(url: str) -> tuple[int, float]:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:  # noqa: BLE001 - connection refused, timeout ...
        status = 0
    return status, time.perf_counter() - start


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--samples", type=int, default=300)
    ap.add_argument("--output", default="docs/evidence/E21-p95-samples.csv")
    args = ap.parse_args()
    if args.samples < 200:
        print("the assignment requires at least 200 samples", file=sys.stderr)
        return 2

    rows = []
    for i in range(args.samples):
        path = PATHS[i % len(PATHS)]
        ts = datetime.now(UTC).isoformat()
        status, seconds = timed_get(args.base_url.rstrip("/") + path)
        rows.append((ts, path, status, round(seconds * 1000, 3)))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "path", "http_status", "latency_ms"])
        w.writerows(rows)

    latencies = sorted(r[3] for r in rows)
    errors = sum(1 for r in rows if not 200 <= r[2] < 300)
    print(f"samples={len(rows)} errors={errors} error_rate={errors / len(rows):.2%}")
    print(
        f"p50={percentile(latencies, 50):.1f}ms p95={percentile(latencies, 95):.1f}ms "
        f"p99={percentile(latencies, 99):.1f}ms max={latencies[-1]:.1f}ms"
    )
    print(f"raw samples: {args.output}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
