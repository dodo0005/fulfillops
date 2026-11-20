## Deliberate bug caught by tests (E12)

**Bug:** `canonical_hash` serialized the request without `sort_keys=True`, so the same order
with JSON keys in a different order produced a different hash. A client retrying its own
order would be told `409 IDEMPOTENCY_CONFLICT`.

**Caught by:** `tests/unit/test_validation.py::test_hash_ignores_key_order` and
`tests/integration/test_idempotency_key_order.py::test_reordered_json_keys_replay_same_order`.

- Red CI run: https://github.com/dodo0005/fulfillops/actions/runs/44765612297/job/136389297044?pr=14
- Green CI run (fix restored): https://github.com/dodo0005/fulfillops/actions/runs/44767761265/job/136396879808?pr=14
- Local output: `docs/evidence/E12-bug-red.txt`, `docs/evidence/E12-bug-green.txt`