# Stealth examples

Runnable, end-to-end examples for `ootle`'s confidential-transfer
(stealth) surface. Stealth crypto — bulletproofs, ElGamal viewable
balances, balance-proof signatures, input-mask aggregation — runs
entirely on the vendored `ootle-wasm` blob (the default crypto
provider). No wallet daemon is required.

## Prerequisites

- A reachable LocalNet **indexer** with a faucet. Point the examples at
  it with `OOTLE_INDEXER_URL` (defaults to the LocalNet URL otherwise):

  ```bash
  export OOTLE_INDEXER_URL=http://localhost:12500
  ```

- Run any example as a module from the repo root:

  ```bash
  uv run python -m examples.stealth.faucet_deposit
  ```

Each example generates fresh keys and faucets its own funds, so they are
self-contained — just run them.

## What each example shows

| File | Stealth features demonstrated |
| ---- | ----------------------------- |
| [`faucet_deposit.py`](faucet_deposit.py) | `OotleWallet.generate_outputs_statement`, `IAsyncFaucet.take_funds_stealth`, reading a UTXO back with `AsyncOotleClient.decrypt_owned_utxo` (AEAD owner-read) |
| [`stealth_to_revealed.py`](stealth_to_revealed.py) | `spend_revealed_input` → `to_revealed_output` (full withdraw / degenerate balance proof), `pay_fee_from_revealed` |
| [`stealth_to_stealth.py`](stealth_to_stealth.py) | `to_stealth_output` + `to_revealed_output` (mixed confidential output + revealed change) |
| [`spend_stealth_utxo.py`](spend_stealth_utxo.py) | `spend_stealth_input`, input-mask aggregation via `AsyncWalletStealthAuthorizer`, `OotleWallet.decrypt_input_data` |
| [`sync_transfer.py`](sync_transfer.py) | the sync mirror — `OotleClient`, `StealthTransfer`, `WalletStealthAuthorizer` with no `await` |

Shared scaffolding (wallet creation, faucet claims, the prepare →
authorize → seal → send flow, and UTXO discovery from the receipt diff)
lives in [`_common.py`](_common.py).

## The transfer flow

Confidential transfers follow the same four-step shape everywhere:

```python
transfer = AsyncStealthTransfer(client, ResourceAddress(TARI_TOKEN))
transfer.spend_revealed_input(account, 4 * TARI)
transfer.to_stealth_output(Output(destination=recipient, amount=TARI, resource_address=...))
transfer.to_revealed_output(2 * TARI)
transfer.pay_fee_from_revealed(TARI)

spec = await transfer.prepare()                                    # build statement + instructions
authorizer = AsyncWalletStealthAuthorizer(wallet, spec, view_secret=secret.view_secret)
hydrated = await authorizer.prepare(client)                        # hydrate + sign balance proof
sealed = client.seal_transaction(hydrated.unsigned)               # seal with the default signer
await (await client.send_transaction(sealed)).watch()             # submit + watch to finality
```

## Notes & limitations

- **Owned stealth UTXOs are read with the AEAD owner-read.**
  `AsyncOotleClient.decrypt_owned_utxo` recovers `(value, mask)` from the
  output's `encrypted_data` with the recipient's view secret — the way a
  recipient reads their own inbound UTXO, viewable resource or not. (The
  ElGamal viewable-balance audit read, for a third party holding only the
  view key, is not part of this client.)
- **`spend_stealth_utxo.py` reports its outcome** rather than asserting
  success: the spend depends on the indexer/engine accepting the balance
  proof for a live UTXO.
- **Receipt access is internal.** Discovering the produced `utxo_…`
  substate reaches into `client._transport.get_transaction_receipt` — the
  public client does not yet surface receipts (a known v1 gap).
- **The sync faucet stealth-deposit** is not shown: the deposit needs
  `OotleWallet.generate_outputs_statement`, which stays async on the
  shared wallet. `sync_transfer.py` seeds with a revealed faucet instead.
- **Two builder variants** have no dedicated file: `pay_fee_from_stealth(component, amount)`
  (pay fees from a stealth account's revealed bucket, instead of
  `pay_fee_from_revealed`) and `with_builder(fn)` (an escape hatch to
  mutate the underlying `TransactionBuilder`). Both chain like the other
  `AsyncStealthTransfer` methods.
