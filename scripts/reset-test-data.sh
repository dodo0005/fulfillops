#!/usr/bin/env bash
# Reset the isolated TEST dataset (no orders, seed stock). Refuses non-test databases.
# Local:   scripts/reset-test-data.sh
# Compose: docker compose exec api python -m common.reset_test_data
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m common.reset_test_data
