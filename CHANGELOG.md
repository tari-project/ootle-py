# Changelog

All notable changes to `ootle` are recorded here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html); pre-1.0
releases may introduce breaking changes between minor versions, but
each is called out below.

## [Unreleased]

Tracks the upstream
[`tari-ootle` v0.53.3](https://github.com/tari-project/tari-ootle/releases/tag/v0.53.3)
release, with the v0.53.1 and v0.53.2 changes.

### Changed

- **Vendored `ootle-wasm` and `ootle-wasm-bor` bumped to 0.53.3.** The 0.53.3
  decoder reads a receipt's `FeeBreakdown` rows in wire order; 0.53.2 rejected
  them when they were not in ascending order.
- **Re-estimate fees** for transactions that pass workspace values as
  arguments: 0.53.2 charges more native execution points for them.

## [0.6.0] — 2026-11-10

Tracks the upstream
[`tari-ootle` v0.53.0](https://github.com/tari-project/tari-ootle/releases/tag/v0.53.0)
release, with the v0.51.0 and v0.52.0 changes. Upstream requires SDKs to
upgrade with the network.

### Changed

- **Vendored `ootle-wasm` and `ootle-wasm-bor` bumped to 0.53.0.** The
  decoder reads `Type::WellKnown` in template definitions built with
  `tari_template_lib` 0.40.

## [0.5.0] — 2026-11-07

Tracks the upstream
[`tari-ootle` v0.50.1](https://github.com/tari-project/tari-ootle/releases/tag/v0.50.1)
release (v0.50.0 plus macOS arm64 builds).

### Changed

- **Vendored `ootle-wasm` and `ootle-wasm-bor` bumped to 0.50.1.**
- **`AbortReason` gains `InputLoadTooLarge`**, for a transaction whose inputs
  in one shard group exceed the 4 MiB per-transaction load cap.

## [0.4.0] — 2026-11-02

Tracks the upstream
[`tari-ootle` v0.49.1](https://github.com/tari-project/tari-ootle/releases/tag/v0.49.1)
release, with the v0.48.0 and v0.49.0 wire changes. Clients before this
release cannot read a 0.48+ indexer or sign for a 0.48+ network.

### Breaking

- **`Address.destination_tag` replaces `Address.memo`**, following upstream's
  PayRef → destination tag rename. The `Address.from_keys(..., destination_tag=...)`
  keyword and `ParsedAddress.destination_tag` are renamed to match. The
  encoded addresses are byte-identical.
- **`CryptoProvider.schnorr_sign` is removed.** The blob no longer exports
  it: transactions are signed with sr25519 inside the blob.
- **`StealthCryptoProvider.stealth_dh_secret` takes the view secret**
  (`network_byte, owner_secret, view_secret, public_nonce`), because 0.48
  derives stealth spend keys from the view key. `LocalSigner` passes its
  own; custom providers and signers must add the parameter.

### Changed

- **Vendored `ootle-wasm` bumped to 0.49.1.**
- **New vendored blob `ootle-wasm-bor` 0.49.1** (about 470 KB). From 0.48 the
  indexer serves substate values, execution results, receipts and events as
  base64 CBOR, and this blob decodes them. It is loaded and hash-checked like
  the main blob, and `make update-wasm` now refreshes both.
- Transactions now carry `main_signer: "SealSigner"` in place of
  `is_seal_signer_authorized`. Stealth inputs now carry a `KeyPath` witness,
  and transfer statements an empty `covenant_claims` list.
- Example and README transfer fees are raised to 10,000 for 0.48 pricing
  (a public transfer now costs about 5.2k).

### Added

- **Proof windows (0.49).** The new `TransactionBuilder.authorize_proof(label)`,
  `drop_proof_authorization(label)` and `with_authorized_proof(label, f)`
  emit the new `AuthorizeProof` / `DropProofAuthorization` instructions.
  Merging builders remaps their workspace ids.
- `AbortReason` covers `GovernanceCallAfterPinnedEpoch`, and
  `ExecutionFailureCode` covers `Conflict`. Before this, an abort for the
  new reason failed to parse.

### Fixed

- **Every indexer read parses the 0.48 responses.** These are
  `GET /substates/{id}` (`state.up.substate`), `POST /substates/fetch` (now
  `{version, value}`), the dry-run `result`, the `execution_result` of
  `GET /transactions/{id}/result`, `GET /transaction-receipts/{id}`, and
  `watch_events()`. A value that does not decode raises `IndexerClientError`;
  `watch_events()` skips such an event.

## [0.3.2] — 2026-10-20

### Changed

- **Vendored `ootle-wasm` bumped to 0.47.0**, tracking the upstream
  [`tari-ootle` v0.47.0](https://github.com/tari-project/tari-ootle/releases/tag/v0.47.0)
  release. The blob's exports are unchanged, but it declares three new
  wasm-bindgen host imports (a `u64 → BigInt` cast, `bigint_get_as_i64` and
  `jsval_eq`), which the bridge now provides. The 0.46 bridge refuses to load
  the new blob.

### Fixed

- **`get_substate()` reads the 0.47 indexer response.** `GET /substates/{id}`
  now returns `state: {up: {substate}}` in place of `substate`, so every
  single-substate fetch failed to parse. A `down` answer (spent version) maps
  to "not found". `POST /substates/fetch` is unchanged.

## [0.3.1] — 2026-10-13

### Changed

- **Vendored `ootle-wasm` bumped to 0.46.0**, tracking the upstream
  [`tari-ootle` v0.46.0](https://github.com/tari-project/tari-ootle/releases/tag/v0.46.0)
  release (protocol V2; non-Esmeralda networks reset). The blob's exports and
  imports are unchanged from 0.43.0, and the indexer endpoints this client
  uses only gained optional fields.

### Fixed

- **`AbortReason` covers `ValidityWindowTooLong` and `InputPledgeTooLarge`.**
  A result aborted for either reason failed to parse with
  `unknown AbortReason variant`.
- **`Amount` instruction arguments encode as a CBOR `u128`** (a plain
  integer, or a tag-2 bignum above `u64::MAX`), matching upstream's
  `minicbor` codec. The old `[lo, hi]` array is refused by the 0.46 engine
  (`unexpected type array ... expected u128`), which broke every `pay_fee`.
- **`watch()` raises promptly when a transaction aborts.** The indexer's
  `TransactionFinalized` event fires only when a receipt commits, and an
  aborted transaction commits none, so `watch()` waited out its whole
  timeout. It now checks the REST result every 2 s while waiting on SSE.
- **A mempool-rejected transaction result parses as a reject.** The
  indexer's `Rejected` result variant raised `TypeError`.
- Default faucet fees in the README and examples raised for 0.46 pricing
  (a faucet take now costs about 1.9k, a stealth faucet about 11.7k).

## [0.3.0] — 2026-10-02

### Changed

- **Vendored `ootle-wasm` bumped to 0.43.0**, tracking the upstream
  [`tari-ootle` v0.43.0](https://github.com/tari-project/tari-ootle/releases/tag/v0.43.0)
  release. The wire changes below arrived in v0.42.0 (a testnet reset); v0.43.0
  leaves the WASM exports and the endpoints this client uses unchanged.
- **Revealed stealth outputs name their receiver.** Upstream replaced
  `StealthOutputsStatement.revealed_output_amount` with
  `revealed_output: RevealedOutput | None` — the amount plus the public key
  whose badge must be in the transaction's auth scope for the engine to create
  the revealed bucket. `revealed_output_amount` survives as a read-only
  property. `StealthOutputsStatement.new_revealed_only` and
  `StealthTransferStatement.revealed_only` now take a `receiver`, and
  `StealthCryptoProvider.generate_outputs_statement` takes a
  `RevealedOutput | None` instead of an amount. `StealthTransfer` and
  `OotleWallet.generate_outputs_statement` (the faucet stealth path) name the
  default account key, which seals the transaction (the wallet helper takes a
  `receiver=` override). `to_revealed_output(0)` is now a no-op instead of an
  error; negative amounts are still rejected, as upstream `Amount` is unsigned.
- **Balance proofs commit to covenant claims.**
  `StealthCryptoProvider.generate_balance_proof_signature` gains a
  `covenant_claims_json` argument; the client builds none, so it signs `"[]"`.
- **Inputs declare read or write intent.** `SubstateRequirement` gains
  `is_write` (default `True`) and serialises as upstream's `InputDeclaration`.
  The resolver declares the resource behind a `VaultForResource` want as a
  read. Upstream now rejects a transaction that declares one substate twice,
  so declarations of the same substate merge (a write if either is; the first
  pinned version wins) instead of appending.
- **`ExecutionFailure` carries a `code`** (`ExecutionFailureCode`), parsed from
  upstream's `{code, message}` payload; `format_reject_reason` renders it as
  `Execution failure (<code>): <message>`. A code newer than this client is
  kept verbatim; the pre-0.42 bare-string form parses as `Unclassified`.

### Added

- **`DiffSummary.downed`** (`DownSubstate`) — substates a transaction consumed
  without replacing (spent UTXOs, confidential outputs).
- `RevealedOutput`, `DownSubstate`, and `ExecutionFailureCode` are exported
  from `ootle`.

## [0.2.0] — 2026-09-17

### Changed

- **Vendored `ootle-wasm` bumped to 0.41.0** (from the locally built
  `0.31.0-local`), tracking the upstream
  [`tari-ootle` v0.41.0](https://github.com/tari-project/tari-ootle/releases/tag/v0.41.0)
  release. The blob's `__wbg_*` host-import names were refreshed to match.
- **`max_epoch` is now mandatory on the wire.** Upstream turned
  `UnsignedTransactionV1.max_epoch` from `Option<Epoch>` into a required
  `Epoch`: every transaction carries a bounded validity window. Builders
  reached through a client (`client.faucet()`, `client.account()`,
  `client.component()`, `StealthTransfer`) default it inside `prepare()` to
  `current_epoch + 10` — one extra `GET /network` round-trip — so existing
  code keeps working. `TransactionBuilder` used standalone must now call
  `with_max_epoch(...)` before `build_unsigned()`, which otherwise raises
  `InvalidArgumentError`. `with_max_epoch()` no longer accepts `None`.
- **Stealth outputs carry `auth` instead of `spend_condition` (TIP-0006).**
  `StealthUnspentOutput.spend_condition` is renamed to
  `StealthUnspentOutput.auth` and now holds a `SpendAuthorization`:
  `{"Key": <one-time pk>}` (was `{"Signed": ...}`), `{"Script": <condition
  root>}`, or `{"KeyAndScript": {...}}`. `Output(pay_to={"AccessRule": ...})`
  consequently produces a `Script` condition-tree root rather than passing the
  access rule through verbatim.

### Added

- **`TransactionBuilder.with_nonce()`** and the `nonce` envelope field, new in
  upstream `UnsignedTransactionV1`. The transaction id excludes the seal
  signature, so two identical bodies sealed by the same key are the *same*
  transaction; stamp a distinct nonce when each submission must execute
  independently. Defaults to `0`, matching upstream.
- **`TransactionBuilder.max_epoch`** — read back the configured bound
  (`None` while unset).

## [0.1.1] — 2026-05-25

### Fixed

- **Project metadata URLs** — corrected the GitHub links in `[project.urls]`
  (`tari-project/ootle-python` → `tari-project/ootle-py`); the old repo name
  did not exist, so the PyPI sidebar "Project links" (Homepage, Documentation,
  Repository, Issues, Changelog) all 404'd.
- **README links** — made the repo-relative links (CHANGELOG, LICENSE,
  CLAUDE.md, the example/script files) absolute so they resolve on the PyPI
  project page, where relative links were being resolved against
  `pypi.org` and breaking.
- **`ootle.__version__`** — resolve the version from the distribution name
  (`ootle-py`) instead of the import name (`ootle`). The old lookup raised
  `PackageNotFoundError` and silently degraded to `"0.0.0+local"` for every
  real install.

## [0.1.0] — 2026-05-21

The first public release. Brings the v1 slice of `ootle-rs` to Python:
an async-first client with a byte-identical sync mirror, both shipped in
a pure-Python `py3-none-any` wheel.

### Added

- **Clients** — `AsyncOotleClient` and the generated sync `OotleClient`,
  over `httpx` + `httpx-sse`.
- **Read-only queries** — account balances (`get_account_balance`,
  `get_account_balances`), substate fetches, and epoch reads against a
  LocalNet indexer.
- **Wallet & signing** — `OotleWallet`, `LocalSigner`, the `Signer`
  protocol, and multi-signer co-authorisation (auto-folded at seal time,
  plus an explicit authorize → attach → seal hand-off).
- **Public transfers** — the `IAccount` builder (`public_transfer`,
  `pay_fee`) and the public XTR faucet (`IFaucet.take_funds`).
- **Component DSL** — the untyped `IComponent` path
  (`call_function` / `call_method`), workspace piping, and the
  `args` / `metadata` / `workspace` instruction helpers.
- **Transaction lifecycle** — `seal_transaction`, `send_transaction`,
  per-pending-tx SSE watching to finality, and `send_dry_run` fee
  estimation.
- **Event watching** — transaction and component event streams with
  `TransactionEventFilter`.
- **Stealth (confidential) transfers** — revealed and stealth
  inputs/outputs in one transfer (`AsyncStealthTransfer`,
  `spend_revealed_input` / `spend_stealth_input` with input-mask
  aggregation, `to_stealth_output` / `to_revealed_output`,
  `pay_fee_from_revealed` / `pay_fee_from_stealth`), the
  `WalletStealthAuthorizer`, the faucet stealth path
  (`IFaucet.take_funds_stealth`), and the `decrypt_owned_utxo` UTXO
  read helper (the AEAD owner-read).
- **Crypto bridge** — the vendored `@tari-project/ootle-wasm` blob
  loaded via `wasmtime`, with SHA-256 verification at load. All
  Ristretto/Schnorr/Borsh and stealth primitives go through it; there is
  no Python-side reimplementation.

### Notes

- Stealth crypto runs entirely on the vendored WASM blob — no wallet
  daemon is required. (An interim wallet-daemon JSON-RPC backend was
  built, proven, then removed once the WASM path landed.)
- Borsh encoding/decoding, HD wallets, BIP-32, and mnemonics are out of
  scope. Typed template bindings (`ootle_template!`) are not included;
  only the untyped component path ships.
