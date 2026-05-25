# ootle

A modern, async-first **Python client library for the Tari L2 network**
(codename _Ootle_). It is the Pythonic counterpart to the Rust crate
`ootle-rs` and the JavaScript package `@tari-project/ootle-wasm`.

> **Status: pre-1.0.** The `0.x.y` API may shift; every breaking change
> is recorded in [`CHANGELOG.md`](https://github.com/tari-project/ootle-py/blob/main/CHANGELOG.md).

## Install

```bash
pip install ootle-py
# or
uv add ootle-py
```

The distribution name on PyPI is **`ootle-py`**; you import it as `ootle`:

```python
from ootle import AsyncOotleClient, OotleClient
```

Requirements: Python **>= 3.13**. The package is pure-Python; the Tari
WASM crypto blob ships inside the wheel — no native build step, and the
same `py3-none-any` wheel runs everywhere.

## Quick start: read-only query

Connect to a LocalNet indexer and read an account balance. No wallet is
needed for read-only queries.

```python
import asyncio
from ootle import (
    AsyncOotleClient, ComponentAddress, Network,
    ResourceAddress, TARI_TOKEN, default_indexer_url,
)


async def main() -> None:
    account = ComponentAddress("component_...your-address...")
    async with AsyncOotleClient.connect(default_indexer_url(Network.LOCAL_NET)) as client:
        balance = await client.get_account_balance(account, ResourceAddress(TARI_TOKEN))
        print(f"TARI balance: {balance}")
        for resource, amount in (await client.get_account_balances(account)).items():
            print(f"  {resource}: {amount}")


asyncio.run(main())
```

Full version: [`examples/balance_query.py`](https://github.com/tari-project/ootle-py/blob/main/examples/balance_query.py)
(and the sync mirror, [`examples/balance_query_sync.py`](https://github.com/tari-project/ootle-py/blob/main/examples/balance_query_sync.py)).

## Quick start: public transfer

Faucet a fresh sender, then transfer TARI to a fresh recipient, watching
each transaction to finalisation. Note that `seal_transaction` is
**synchronous** — only the I/O calls are awaited.

```python
import asyncio
from ootle import (
    AsyncOotleClient, LocalSigner, Network, OotleSecretKey,
    OotleWallet, ResourceAddress, TARI, TARI_TOKEN, default_indexer_url,
)


async def main() -> None:
    sender = OotleSecretKey.random(Network.LOCAL_NET)
    wallet = OotleWallet(default=LocalSigner(sender))
    resource = ResourceAddress(TARI_TOKEN)
    async with AsyncOotleClient.connect(
        default_indexer_url(Network.LOCAL_NET), wallet=wallet
    ) as client:
        # Faucet the public XTR faucet's fixed dispense into the sender.
        funded = await client.faucet().take_funds().pay_fee(500).prepare()
        await (await client.send_transaction(client.seal_transaction(funded))).watch()

        # Transfer 2 TARI to a fresh recipient.
        recipient = OotleSecretKey.random(Network.LOCAL_NET).to_address()
        unsigned = await (
            client.account()
            .pay_fee(1000)
            .public_transfer(recipient, resource, 2 * TARI)
            .prepare()
        )
        sealed = client.seal_transaction(unsigned)
        await (await client.send_transaction(sealed)).watch()


asyncio.run(main())
```

Register extra signers with `wallet.register(LocalSigner(...))` and they
are folded in automatically at seal time (multi-signer co-authorisation);
`manual_co_signing.py` shows the explicit authorize → attach → seal
hand-off for remote-signer / HSM setups. Estimate fees first with
`await client.send_dry_run(unsigned)`. Full file:
[`examples/fungible_transfer.py`](https://github.com/tari-project/ootle-py/blob/main/examples/fungible_transfer.py).

## Stealth (confidential) transfers

Confidential transfers run **entirely on the vendored `ootle-wasm`
blob** — the default crypto provider. Bulletproofs, ElGamal viewable
balances, balance-proof signatures, and input-mask aggregation all
execute locally; **no wallet daemon or external service is required.**

Build the transfer, hydrate the balance proof with an
`AsyncWalletStealthAuthorizer`, then seal with the wallet's default
signer:

```python
import asyncio
from ootle import (
    AsyncOotleClient, AsyncStealthTransfer, AsyncWalletStealthAuthorizer,
    LocalSigner, Network, OotleSecretKey, OotleWallet, Output,
    ResourceAddress, TARI, TARI_TOKEN, default_indexer_url,
)


async def main() -> None:
    sender = OotleSecretKey.random(Network.LOCAL_NET)
    wallet = OotleWallet(default=LocalSigner(sender))
    resource = ResourceAddress(TARI_TOKEN)
    recipient = OotleSecretKey.random(Network.LOCAL_NET).to_address()
    async with AsyncOotleClient.connect(
        default_indexer_url(Network.LOCAL_NET), wallet=wallet
    ) as client:
        # ... faucet the sender first (see examples/stealth/) ...
        transfer = AsyncStealthTransfer(client, resource)
        transfer.spend_revealed_input(sender.to_address().to_component_address(), 5 * TARI)
        transfer.to_stealth_output(
            Output(destination=recipient, amount=4 * TARI, resource_address=resource)
        )
        transfer.to_revealed_output(TARI)
        transfer.pay_fee_from_revealed(500)

        spec = await transfer.prepare()
        authorizer = AsyncWalletStealthAuthorizer(
            wallet, spec, view_secret=sender.view_secret
        )
        hydrated = await authorizer.prepare(client)
        sealed = client.seal_transaction(hydrated.unsigned)
        await (await client.send_transaction(sealed)).watch()


asyncio.run(main())
```

Stealth supports revealed and stealth inputs and outputs, mixed in one
transfer: `spend_revealed_input` / `spend_stealth_input` (with input-mask
aggregation) feed `to_stealth_output` / `to_revealed_output`, with fees
paid from a revealed bucket (`pay_fee_from_revealed`) or a stealth
account's revealed vault (`pay_fee_from_stealth`). The public faucet has
a stealth path too (`IFaucet.take_funds_stealth`), and owned UTXOs are
read back with `AsyncOotleClient.decrypt_owned_utxo` (AEAD owner-read).

The full set of runnable stealth examples — faucet deposit,
stealth↔revealed, stealth↔stealth, spending an owned UTXO, and the sync
mirror — lives in [`examples/stealth/`](https://github.com/tari-project/ootle-py/blob/main/examples/stealth/README.md).

## Sync vs. async

Every async API has a sync mirror with the same shape. Swap the imports
and drop the `await`s:

```python
from ootle import OotleClient                  # sync
from ootle import AsyncOotleClient             # async
```

The sync names mirror the async ones — `IAccount` / `IAsyncAccount`,
`StealthTransfer` / `AsyncStealthTransfer`, `PendingTransaction` /
`AsyncPendingTransaction`, and so on. The sync tree is **generated** from
the async source by [`scripts/unasync.py`](https://github.com/tari-project/ootle-py/blob/main/scripts/unasync.py) and
committed; CI asserts the two trees stay byte-identical. Both ship in the
wheel.

## Running the examples

The examples are self-contained — each generates fresh keys and faucets
its own funds against a LocalNet indexer:

```bash
OOTLE_INDEXER_URL=http://localhost:12500 \
uv run python -m examples.fungible_transfer
```

See [`examples/README.md`](https://github.com/tari-project/ootle-py/blob/main/examples/README.md) and
[`examples/stealth/README.md`](https://github.com/tari-project/ootle-py/blob/main/examples/stealth/README.md) for the full
catalogue and the few examples that need an external artifact (a deployed
template, a live component to watch, …).

## Logging

Every internal module emits diagnostics under the `ootle.*` logger
namespace. The library installs a `NullHandler` on `ootle` so
unconfigured callers see nothing; opt in by configuring `logging`:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("ootle").setLevel(logging.DEBUG)
```

Useful sub-namespaces:

- `ootle._async._transport` / `ootle._sync._transport` — request paths.
- `ootle._async._watcher` / `ootle._sync._watcher` — SSE open/close, fallbacks.
- `ootle._async._resolver` / `ootle._sync._resolver` — chunked substate fetches.
- `ootle._crypto._wasm_runtime` — WASM blob load + SHA-256 verification.
- `ootle.wallet` — multi-signer co-authorisation traces.

## Scope

**In v1:** read-only queries · the public XTR faucet · public transfers
(`IAccount`) · multi-signer co-authorisation · the untyped component DSL
(`IComponent.call_function` / `call_method`) · dry-run fee estimation ·
transaction and component event watching · confidential **stealth
transfers** (revealed + stealth inputs/outputs, input-mask aggregation,
the faucet stealth path, and UTXO read helpers), all backed by the
vendored WASM blob.

**Not in v1:**

- **Typed templates / `ootle_template!`** — only the untyped
  `IComponent` path ships; there is no codegen for typed bindings.
- **HD wallets, BIP-32, mnemonics** — caller-application concerns.
- **Borsh in Python** — all Borsh encoding/decoding is delegated to the
  WASM blob, never reimplemented in Python.

## Contributing

The engineering contract — including the **200-line file limit** and the
strict typing rules — is in [`CLAUDE.md`](https://github.com/tari-project/ootle-py/blob/main/CLAUDE.md).

```bash
make sync          # bootstrap the venv
make ci            # the gate the pipeline runs
make unasync       # regenerate src/ootle/_sync/ from _async/
```

After any change under `src/ootle/_async/`, run `make unasync` and commit
the regenerated `_sync/` mirror in the same commit — `make ci` fails on
drift.

## License & acknowledgements

Released under the **BSD 3-Clause** license — see [`LICENSE`](https://github.com/tari-project/ootle-py/blob/main/LICENSE).

The vendored WASM blob is built from
[`@tari-project/ootle-wasm`](https://www.npmjs.com/package/@tari-project/ootle-wasm)
and ships inside the wheel under
`src/ootle/_crypto/wasm/ootle_wasm_bg.wasm`, with its upstream version
and SHA-256 recorded in `VERSION` and verified at load.
