# 10 — External Dependencies

`ootle-rs` is a thin façade — most weight sits in upstream crates. This
doc lists every direct dependency from `Cargo.toml`, what each provides,
and a flag for porting effort: **D** (data shape: re-buildable in Python
with serde-equivalent encoding), **C** (cryptographic logic: significant
implementation), **I** (infrastructure: standard library replacement).

## Tari workspace crates

| Crate                       | Effort | What it provides                                                                                                               |
|-----------------------------|:------:|--------------------------------------------------------------------------------------------------------------------------------|
| `tari_ootle_common_types`   | D      | `Network`, `Epoch`, `Substate`, `SubstateId`, `SubstateValue`, `ExecuteResult`, `RejectReason`, `TransactionResult`, `FinalizeOutcome`, `TransactionReceipt`, `IndexedWellKnownTypes`, `ValueLookupTable` trait, `ElgamalVerifiableBalance`, domain hashers (`WalletOutputEncryptionKeysDomainHasher`), `SubstateRequirement`. |
| `tari_ootle_transaction`    | D + C  | `Transaction`, `UnsignedTransaction`, `UnsealedTransaction`, `TransactionEnvelope` (Borsh codec), `TransactionId`, `TransactionSignature`, `TransactionSealSignature`, `Signable` trait (the `to_signing_message` prehash builder), `TransactionBuilder`, instructions (`call_function`, `call_method`, `pay_fee_from_*`, `stealth_transfer`, etc.), workspace plumbing, named args. |
| `tari_template_lib_types`   | D      | `Amount`, `ComponentAddress`, `ResourceAddress`, `UtxoAddress`, `UtxoId`, `VaultId`, `TemplateAddress`, `FunctionName`, `EncryptedData`, `PedersenCommitmentBytes`, `RistrettoPublicKeyBytes`, `UtxoTag`, the `stealth::*` statement types (`StealthInput`, `StealthInputsStatement`, `StealthOutputsStatement`, `StealthTransferStatement`, `StealthUnspentOutput`, `UnspentOutput`, `SpendCondition`), constants (`TARI`, `TARI_TOKEN`, `XTR_FAUCET_*`).  Activated features: `extra-arith`, `borsh`. |
| `tari_ootle_wallet_crypto`  | C      | The hardest porting target. Provides: `kdfs::{owner_stealth_dh_secret, dh_kdf_aead, encrypted_data_dh_kdf_aead}`, `bullet_proof::generate_extended_bullet_proof`, `viewable_balance_proof::generate_elgamal_viewable_balance_proof`, `balance_proof::{generate_stealth_balance_proof_signature, validate_balance_proof_signature}`, `encrypted_data::unblind_output`, `StealthCryptoApi` (stealth pubkey + UTXO tag derivation, AEAD encryption), `OutputWitness`, `StealthOutputWitness`, `DecryptedData`, `Memo`, `PayTo`, value-lookup tables (`MMapValueLookup` behind `mmap-value-lookup` feature), error types `StealthProofError`, `StealthCryptoApiError`. Also re-exported as `ootle_rs::crypto`. |
| `tari_crypto`               | C      | `RistrettoPublicKey`, `RistrettoSecretKey`, `RistrettoSchnorr` Schnorr signatures, key generation, hex utilities (`tari_utilities::hex::Hex`).                                                                                                |
| `tari_bor`                  | I      | Borsh wrapper used by `TransactionEnvelope::encode/decode`. Errors surface as `tari_bor::BorError`.                                                                                                                                          |
| `ootle_byte_type`           | I      | `ToByteType`, `FromByteType`, `ConvertFromByteType` — strongly-typed byte-array conversions used everywhere `RistrettoPublicKey` ↔ `RistrettoPublicKeyBytes` etc.                                                                            |
| `tari_indexer_client`       | D + I  | `IndexerRestApiClient`, `connect_rest`, request/response types (`SubmitTransactionRequest`, `GetSubstateRequest`, `GetSubstatesRequest`, `GetTransactionResultRequest`, `IndexerTransactionFinalizedResult`, `StreamTransactionEventsRequest`, `TransactionEvent`, `TransactionFinalizedEvent`), SSE client (`sse::Event`, `sse_events`, `sse_transaction_events`), error type `IndexerRestClientError`. Activated feature: `client`. |
| `tari_ootle_address`        | D      | `OotleAddress`, `RistrettoOotleAddress`, `address!` macro for parsing `otl_loc_…` strings.                                                                                                                                                   |
| `tari_template_builtin`     | D      | `ACCOUNT_TEMPLATE_ADDRESS` and other built-in template addresses.                                                                                                                                                                            |

## Generic Rust crates

| Crate                | Effort  | Used for                                                                            |
|----------------------|:-------:|-------------------------------------------------------------------------------------|
| `tokio`              | I       | Async runtime; `sync` (mpsc, oneshot, watch, OnceLock indirectly), `macros`, `task`, `time::sleep_until`, `task::spawn_blocking`. |
| `async-trait`        | I       | `dyn`-compatibility for the four signing traits.                                    |
| `async-stream`       | I       | `async_stream::stream! { … }` macro for SSE stream construction.                    |
| `futures`            | I       | `Stream`, `StreamExt`, `BoxStream`, `FutureExt`.                                    |
| `indexmap`           | I       | `IndexSet<StealthSignerRequirement>` (insertion order matters for fee-spending).    |
| `rand`               | I       | `thread_rng()`, `CryptoRng`, used everywhere a Ristretto secret is generated.       |
| `thiserror`          | I       | All error enums.                                                                    |
| `serde`/`serde_json` | I       | JSON serialisation for the indexer client; `Signed<T>` derive.                      |
| `tracing`            | I       | Span/log instrumentation (debug/info/warn/error).                                   |
| `signature` 3.0.0-rc.8 | I     | `PrehashSigner`, `Keypair` traits used by `OotleSecretKey`. Pinned exact version.   |

## Cargo features

```toml
[features]
default = []
mmap-value-lookup = ["tari_ootle_wallet_crypto/mmap-value-lookup"]
```

The only feature, `mmap-value-lookup`, forwards to upstream and enables a
memory-mapped ElGamal value lookup table for fast UTXO decryption (see
`07-cryptography.md`).

## Porting effort summary

For a Python port:

- **Trivial** (replace with stdlib/asyncio + a Python HTTP client): `tokio`,
  `async-trait`, `async-stream`, `futures`, `indexmap`, `rand`, `thiserror`,
  `tracing`, `serde_json`, `signature`.
- **Moderate** — reproduce data shapes & wire format:
  `tari_ootle_common_types`, `tari_ootle_transaction` (Borsh!),
  `tari_template_lib_types`, `tari_ootle_address`, `tari_template_builtin`,
  `tari_indexer_client` (request/response shapes + SSE).
  Borsh has a Python implementation but the exact derives in the upstream
  Rust types must be reproduced field-by-field.
- **Hard** — reimplement or bind:
  - `tari_crypto` (Ristretto + Schnorr): no first-class Python binding
    today. Either bind via `pyo3`/`maturin`, or use a curve25519 lib +
    write the Tari-flavoured Schnorr challenge construction manually.
  - `tari_ootle_wallet_crypto` (Bulletproofs, ElGamal viewable balance,
    balance proofs, AEAD-encrypted data, stealth pubkey derivation,
    domain-separated KDFs): the tallest mountain. The pragmatic v1
    Python wallet would either ship a `pyo3` extension wrapping this
    crate, or omit stealth entirely and support only public transfers.
  - `tari_bor` (Borsh): closest Python equivalent is the `borsh` package
    on PyPI, but layouts must match exactly.

The "Core / Transport / Provider / Signer" layering from the upstream
README maps directly: Core ≈ `template_lib_types` + `common_types` +
`address`; Transport ≈ `indexer_client`; Provider ≈ this crate's
`provider/` module; Signer ≈ `tari_crypto` + `signature` + this crate's
`signer/` and `key_provider/`.
