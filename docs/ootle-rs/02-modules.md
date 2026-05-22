# 02 — Module Catalog

The crate has 33 source files in `src/` totalling ~4,900 LOC, plus 4 example
programs. Below, each module/file is summarised with line count, purpose,
key public types, and which other in-crate modules it depends on. Lines
counts are exact (`wc -l` on commit at time of writing).

> Heads-up: `src/signer/local_signer/` (mod.rs + private_key.rs, ~114 LOC)
> exists on disk but is **not compiled** — `signer/mod.rs:5` has
> `// pub mod local_signer;` commented out. The active per-key signer code
> lives in `key_provider/local/` and `key_provider/local/generic_impls.rs`.

## `lib.rs` (25 lines)

Module tree and re-exports. Public modules: `builtin_templates`,
`key_provider`, `provider`, `signer`, `transaction`, `wallet`, `macros`,
`keys`, `stealth`. Re-exports `Network`, `displayable` from
`tari_ootle_common_types`; aliases `tari_ootle_wallet_crypto` as `crypto`
and `tari_template_lib_types` as `template_types`; re-exports
`address!` macro and the contents of `helpers` and `types`.

## `helpers.rs` (15 lines)

`default_indexer_url(Network) -> &'static str`: hardcoded URLs per network
(LocalNet → `http://localhost:12500`, Esmeralda → fixed IP). MainNet,
StageNet, NextNet, Igor are `unimplemented!()`. Also defines `ToAccountAddress`
trait re-exported from `types/address.rs`.

## `provider/` (~1,170 LOC) — the bulk of the API

| File                        | Lines | Purpose                                                                                            |
|-----------------------------|------:|----------------------------------------------------------------------------------------------------|
| `mod.rs`                    |    22 | Re-exports public surface                                                                          |
| `traits.rs`                 |    52 | `Provider`, `WalletProvider` traits                                                                |
| `builder.rs`                |    64 | `ProviderBuilder<Wallet>`, `connect`, `connect_with_transaction_timeout`                           |
| `indexer.rs`                |   228 | `IndexerProvider<Wallet>`: `get_network`, `fetch_substate(s)`, `send_transaction`, dry-run, etc.   |
| `balance.rs`                |   189 | `VaultBalance`, `get_account_balance`, `get_account_balances`, `decrypt_stealth_utxo_values`       |
| `input_resolver.rs`         |   375 | `TransactionInputResolver`: turn a `HashSet<WantInput>` into `UnsignedTransaction` inputs          |
| `event_watcher.rs`          |   112 | `TransactionEventStream`: SSE subscription for template events                                     |
| `tx_stream.rs`              |   168 | `EventStream`, `Paused`, `PauseWaiter`: pausable inner SSE stream feeding the tx watcher           |
| `tx_watcher.rs`             |   492 | `TransactionWatcher`, `TransactionWatcherHandle`, `PendingTransaction`, `PendingTransactionOutcome`|
| `error.rs`                  |    38 | `ProviderError` enum (thiserror)                                                                   |
| `want_input.rs`             |    22 | `WantInput` enum (resolver request shape)                                                          |

Intra-crate deps: depends on `wallet/` (for `NetworkWallet`), `Address`,
`TransactionOutcome`, `signer` types, and the input resolver feeds back into
`provider/indexer.rs`.

## `wallet/` (~280 LOC)

| File         | Lines | Purpose                                                                                       |
|--------------|------:|-----------------------------------------------------------------------------------------------|
| `mod.rs`     |    14 | Re-exports                                                                                    |
| `traits.rs`  |    28 | `NetworkWallet` trait + composite `WalletKeyProvider` blanket impl                            |
| `ootle.rs`   |   225 | `OotleWallet` (multi-signer store), `TransactionAuthorization`, default `NetworkWallet` impl  |
| `stealth.rs` |   127 | `WalletStealthAuthorizer`: orchestrates stealth-key authorisations and seal signing           |
| `none.rs`    |     5 | `NoWallet` zero-sized type for builder default                                                |
| `error.rs`   |    18 | `WalletError` enum                                                                            |

Depends on `key_provider/`, `signer/`, `stealth/`, `transaction/`, `types/`.

## `key_provider/` (~390 LOC)

| File                   | Lines | Purpose                                                                                  |
|------------------------|------:|------------------------------------------------------------------------------------------|
| `mod.rs`               |    10 | Re-exports                                                                               |
| `traits.rs`            |    19 | `OutputMaskProvider`, `DiffieHellmanKdfKeyProvider<H>`                                   |
| `error.rs`             |    15 | `KeyProviderError` (boxed `dyn Error`)                                                   |
| `local/mod.rs`         |    24 | `LocalKeyProvider<C>` generic over credential type                                       |
| `local/private_key.rs` |    34 | `PrivateKeyProvider` (= `LocalKeyProvider<OotleSecretKey>`) + `random(network)`          |
| `local/generic_impls.rs`|  303 | `TransactionSigner`, `DiffieHellmanKdfKeyProvider`, `StealthOutputStatementFactory`, `InputDecryptor`, `TransactionStealthKeySigner` for `LocalKeyProvider<C>`; `create_output_witness` |

Provides every concrete wallet-side implementation. `PrivateKeyProvider` is
the type you usually instantiate.

## `signer/` (~36 LOC compiled)

| File             | Lines | Purpose                                                              |
|------------------|------:|----------------------------------------------------------------------|
| `mod.rs`         |     9 | Re-exports `error`, `stealth_key`. `local_signer` is commented out.  |
| `error.rs`       |    20 | `SignerError`, `Result<T>` alias                                     |
| `stealth_key.rs` |    16 | `StealthKeyPrehashSigner<S>` trait                                   |

The dormant `signer/local_signer/` directory (114 lines) duplicates parts of
`key_provider/local` — historical artefact.

## `transaction/` (~79 LOC)

| File                   | Lines | Purpose                                                                                              |
|------------------------|------:|------------------------------------------------------------------------------------------------------|
| `mod.rs`               |     7 | Re-exports                                                                                           |
| `signer.rs`            |    47 | `TransactionSigner`, `TransactionSealSigner`, `TransactionStealthKeySigner` traits                   |
| `ephemeral_signer.rs`  |    32 | `EphemeralKeySigner`: random Ristretto secret, used to seal pure-stealth txs that need no specific signer |

## `keys/` (~133 LOC)

| File         | Lines | Purpose                                                                                  |
|--------------|------:|------------------------------------------------------------------------------------------|
| `mod.rs`     |     8 | Re-exports                                                                               |
| `traits.rs`  |    10 | `HasViewOnlyKeySecret`                                                                   |
| `secret.rs`  |   115 | `OotleSecretKey {network, account_secret, view_only_secret}`, `to_address`, prehash signers |

`OotleSecretKey` implements `PrehashSigner`, `StealthKeyPrehashSigner`,
`HasViewOnlyKeySecret`, `Keypair`, and `OutputMaskProvider`. It is the
single concrete type used throughout the crate.

## `stealth/` (~700 LOC)

| File          | Lines | Purpose                                                                                              |
|---------------|------:|------------------------------------------------------------------------------------------------------|
| `mod.rs`      |    12 | Re-exports                                                                                           |
| `traits.rs`   |    40 | `StealthOutputStatementFactory`, `InputDecryptor`, `StealthSigner`, `StealthProvider`                |
| `error.rs`    |    45 | `StealthProviderError`, `InvalidStealthInputError`                                                   |
| `spec.rs`     |   246 | `Output` (transfer destination), `SignatureRequirements`, `StealthSignerRequirement`, invariant tests|
| `builder.rs`  |   267 | `StealthTransfer<'a, P>` builder; `prepare` produces `(StealthTransferStatement, SignatureRequirements)` |

## `builtin_templates/` (~556 LOC)

| File            | Lines | Purpose                                                                       |
|-----------------|------:|-------------------------------------------------------------------------------|
| `mod.rs`        |     9 | Re-exports                                                                    |
| `traits.rs`     |    17 | `UnsignedTransactionBuilder` (shared `prepare()` shape)                       |
| `account.rs`    |   127 | `IAccount` / `AccountInvokeBuilder`: `pay_fee`, `public_transfer`, `publish_template`|
| `faucet.rs`     |   177 | `IFaucet` / `FaucetInvokeBuilder`: `take_faucet_funds`, `take_faucet_funds_stealth`, `take_max_faucet_funds`|
| `component.rs`  |   233 | `IComponent` / `ComponentInvokeBuilder`, `OotleInvoke` trait, `IntoBuildParts`, `TemplateInterface`/`ComponentInterface` markers, `chain` for cross-builder composition |

## `types/` (~88 LOC)

| File                       | Lines | Purpose                                                                       |
|----------------------------|------:|-------------------------------------------------------------------------------|
| `mod.rs`                   |    14 | Re-exports + `pub type Signature = TransactionSealSignature`                  |
| `address.rs`               |    18 | `pub type Address = tari_ootle_address::OotleAddress` + `ToAccountAddress`    |
| `signed.rs`                |    28 | Generic `Signed<T>{tx, signature}` wrapper (currently unused by API)          |
| `transaction/mod.rs`       |     8 | Re-exports                                                                    |
| `transaction/request.rs`   |    61 | `TransactionRequest<State>` type-state builder (`Initial` / `WithTx`)         |
| `transaction/outcome.rs`   |    47 | `TransactionOutcome` enum (`Commit` / `OnlyFeeCommit` / `Reject`)             |

## `macros.rs` (549 lines — exempt-but-still-large)

`resource_address!()` and `ootle_template!()` declarative macros, plus the
hidden `__ootle_template_inner!` parser. Generates a `MyTemplate<'a, P, I>`
wrapper struct with two interface markers (`TemplateInterface`,
`ComponentInterface`) and typed methods that produce
`ComponentInvokeBuilder`. Re-exports for use sites are namespaced under
`crate::macros::_macro_exports`.

This file is the largest single file in the crate. A Python port would not
have an equivalent macro system; the mechanism this provides (typed
interface to a deployed template) maps to a Python class generator or
codegen tool driven from a template manifest.
