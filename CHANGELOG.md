# Changelog

All notable changes to `ootle` are recorded here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html); pre-1.0
releases may introduce breaking changes between minor versions, but
each is called out below.

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
