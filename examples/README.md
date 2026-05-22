# ootle examples

Runnable, end-to-end examples for the `ootle` client. They mirror the
public-path slices of `ootle-rs/examples/` and exercise the real wire
protocol against a LocalNet indexer.

## Prerequisites

- A reachable LocalNet **indexer** with a faucet. Point the examples at
  it with `OOTLE_INDEXER_URL` (defaults to the LocalNet URL otherwise):

  ```bash
  export OOTLE_INDEXER_URL=http://localhost:12500
  ```

- Run any example as a module from the repo root:

  ```bash
  uv run python -m examples.fungible_transfer
  ```

## Self-contained by design

Every example generates its own fresh keys and faucets its own funds via
the shared scaffolding in [`_common.py`](_common.py) — wallet creation,
the indexer-URL helper, faucet claims, the `prepare → seal → send → watch`
dance, and new-substate extraction. No pre-existing wallets, accounts, or
recipient addresses are required.

The stealth examples build on the same base: see
[`stealth/README.md`](stealth/README.md) and
[`stealth/_common.py`](stealth/_common.py).

### URL-only examples

These need nothing but `OOTLE_INDEXER_URL`:

| File | Shows |
| ---- | ----- |
| [`balance_query.py`](balance_query.py) | faucet a fresh account, then read its balances (`get_account_balance` / `get_account_balances`) |
| [`balance_query_sync.py`](balance_query_sync.py) | the same, using the blocking `OotleClient` (sync mirror) |
| [`fungible_transfer.py`](fungible_transfer.py) | faucet → dry-run → public transfer to fresh recipients, with a registered co-signer (implicit multi-signer) |
| [`dry_run_only.py`](dry_run_only.py) | fee estimation without committing — both the commit and reject paths |
| [`manual_co_signing.py`](manual_co_signing.py) | explicit authorize → attach → seal hand-off (the remote-signer / HSM pattern) |
| [`workspace_chain.py`](workspace_chain.py) | bucket flow via workspace piping plus the raw-builder `.then()` escape hatch |

### Examples that need an external artifact

These reuse the same framework but require an additional input:

| File | Also needs |
| ---- | ---------- |
| [`counter_deploy.py`](counter_deploy.py) | `OOTLE_COUNTER_TEMPLATE=template_<hex>` (a deployed Counter template) |
| [`template_invoke.py`](template_invoke.py) | `OOTLE_STABLECOIN_TEMPLATE=template_<hex>` or `OOTLE_STABLECOIN_COMPONENT=component_<hex>` |
| [`publish_template.py`](publish_template.py) | `OOTLE_TEMPLATE_WASM=/path/to/template.wasm` (a compiled template) |
| [`watch_component_events.py`](watch_component_events.py) | `OOTLE_COMPONENT_ADDRESS=component_<hex>` (a live component to watch) |

`publish_template.py` is the bootstrap: run it once to publish a WASM
template and it prints the `OOTLE_COUNTER_TEMPLATE=…` line to feed into
the others.

## Testing

The URL-only examples are smoke-tested in
[`tests/integration/test_examples.py`](../tests/integration/test_examples.py)
(marker-gated). Run them with:

```bash
OOTLE_INDEXER_URL=http://localhost:12500 uv run pytest -m integration
```
