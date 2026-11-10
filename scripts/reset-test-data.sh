#!/usr/bin/env bash
# Safe test-only reset (Compose). common.reset_test_data refuses unless
# APP_ENV=test AND the database name contains "test".
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
docker compose exec -T api python -m common.reset_test_data
