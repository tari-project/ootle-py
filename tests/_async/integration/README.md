# Integration tests

These tests exercise the full async + sync clients against a **running
Tari L2 indexer** (typically a LocalNet). They are gated by the
`integration` pytest marker and skipped by default — `make ci` does not
run them.

## Running

```bash
OOTLE_INDEXER_URL=http://localhost:12500 \
  uv run pytest -m integration tests/
```

Optional:

- `OOTLE_TEST_ACCOUNT` — a component address (`component_…`) that the
  test should query. Defaults to a placeholder when unset; the test
  only asserts the call shape.

The sync mirror in `tests/_sync/integration/` is generated from this
folder by `make unasync`. Run both as one command:

```bash
OOTLE_INDEXER_URL=http://localhost:12500 \
  uv run pytest -m integration
```
