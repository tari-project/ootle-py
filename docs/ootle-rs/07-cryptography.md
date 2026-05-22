# 07 — Cryptography

## Primitives

`ootle-rs` consumes — but does not implement — the cryptographic
primitives below. All of them come from upstream crates:

| Primitive                     | Source crate                       | Used for                                                |
|-------------------------------|------------------------------------|---------------------------------------------------------|
| Ristretto255 keypair          | `tari_crypto::ristretto`           | All account & view-only secrets                         |
| Schnorr signatures (Ristretto)| `tari_crypto::ristretto::RistrettoSchnorr` | Transaction sealing & authorisation              |
| Pedersen commitments          | `tari_template_lib_types::crypto`  | UTXO value hiding                                       |
| Bulletproofs (range proofs)   | `tari_ootle_wallet_crypto::bullet_proof::generate_extended_bullet_proof` | Stealth output amounts in [0, 2^64) |
| ElGamal viewable balance proof| `tari_ootle_wallet_crypto::viewable_balance_proof` | View-key holders can decrypt UTXO values  |
| AEAD-encrypted output data    | `tari_ootle_wallet_crypto::encrypted_data` | Memo + value blinding for stealth UTXOs         |
| KDFs (DH-style)               | `tari_ootle_wallet_crypto::kdfs`   | Stealth-key derivation, output decryption keys          |
| Signature trait abstraction   | `signature` crate (3.0.0-rc.8)     | `PrehashSigner` / `Keypair` glue                        |
| Domain-separated hashing      | `tari_ootle_common_types::base_layer_hashing` | `WalletOutputEncryptionKeysDomainHasher`     |

Note the version pin: `signature = "3.0.0-rc.8"` is exact in
`Cargo.toml:32`. The trait shape that ships in 3.0.0 stable would not
necessarily match.

## The single key type: `OotleSecretKey`

```rust
// crates/wallet/ootle-rs/src/keys/secret.rs:24-29
pub struct OotleSecretKey {
    network: Network,
    account_secret: RistrettoSecretKey,    // signs transactions
    view_only_secret: RistrettoSecretKey,  // decrypts inbound stealth UTXOs
}
```

This one struct carries every secret a wallet needs. It implements:

- `PrehashSigner<(RistrettoSchnorr, RistrettoPublicKey)>` — non-stealth
  Schnorr signing over the account secret (`secret.rs:71-77`).
- `StealthKeyPrehashSigner<(RistrettoSchnorr, RistrettoPublicKey)>` —
  stealth signing: derives a per-output secret via
  `kdfs::owner_stealth_dh_secret(network, account_secret, public_nonce)`,
  then Schnorr-signs the prehash with the derived secret
  (`secret.rs:80-92`).
- `HasViewOnlyKeySecret` — exposes `&view_only_secret` for ElGamal
  decryption and DH KDFs (`secret.rs:94-98`).
- `Keypair` (from the `signature` crate) — `verifying_key()` returns the
  account public key (`secret.rs:100-106`).
- `OutputMaskProvider` — `next_mask().await` returns a fresh random
  Ristretto secret to use as a Pedersen commitment mask
  (`secret.rs:108-115`). The doc comment notes this is intentionally
  non-deterministic; a hardware-backed wallet might derive masks instead.

The Ristretto address bytes that flow over the wire are produced via
`OotleAddress::new(network, view_only_pk.to_byte_type(),
account_pk.to_byte_type())` in `to_address()` (`secret.rs:64-68`).

## The key-provider wrapper: `LocalKeyProvider<C>`

```rust
// crates/wallet/ootle-rs/src/key_provider/local/mod.rs
pub struct LocalKeyProvider<C> { address: Address, credentials: C }

// crates/wallet/ootle-rs/src/key_provider/local/private_key.rs
pub type PrivateKeyProvider = LocalKeyProvider<OotleSecretKey>;
pub type PrivateKeySigner   = PrivateKeyProvider;          // alloy-style alias
```

`generic_impls.rs` (303 lines, see `02-modules.md`) implements every
wallet capability for `LocalKeyProvider<C>` *parameterised by what `C`
itself provides*:

- `TransactionSigner` for any `C: PrehashSigner<(RistrettoSchnorr,
  RistrettoPublicKey)>`. `sign_transaction` and `sign_authorization`
  both call `to_signing_message(...)` on the unsigned/unsealed tx and
  delegate to `C::sign_prehash` (`generic_impls.rs:57-82`).
- `DiffieHellmanKdfKeyProvider<WalletOutputEncryptionKeysDomainHasher>`
  for any `C: HasViewOnlyKeySecret`. Wraps `kdfs::dh_kdf_aead`
  (`generic_impls.rs:84-99`).
- `StealthOutputStatementFactory` for any `C: OutputMaskProvider`.
  Constructs `StealthUnspentOutput`s and an aggregate range proof
  (`generic_impls.rs:101-157`). Delegates to
  `tari_ootle_wallet_crypto::StealthCryptoApi` for stealth-address
  derivation and AEAD-encrypted data, then runs
  `generate_extended_bullet_proof` on a blocking thread pool via
  `tokio::task::spawn_blocking`.
- `InputDecryptor` for any `C: HasViewOnlyKeySecret`. Recovers the
  per-output encryption key via DH-AEAD KDF and unblinds the output's
  encrypted data (`generic_impls.rs:159-195`).
- `TransactionStealthKeySigner` for any `C: StealthKeyPrehashSigner<…>`
  (`generic_impls.rs:272-303`).

`OotleSecretKey` satisfies all of `PrehashSigner`, `OutputMaskProvider`,
`HasViewOnlyKeySecret`, `StealthKeyPrehashSigner`, so
`PrivateKeyProvider = LocalKeyProvider<OotleSecretKey>` ends up
implementing the whole `WalletKeyProvider` composite (per the blanket
impl in `wallet/traits.rs:27-28`).

## Three signing flavors

Three different signature operations come out of the wallet at different
points in a transaction's lifecycle:

1. **`sign_authorization`** (`TransactionSigner`) — produces a
   `TransactionAuthorization` (wrapped `TransactionSignature`) over the
   prehash `tx.to_signing_message(seal_signer)`. Bound to a *specific*
   `seal_signer` public key, so co-signers commit to who will seal.
2. **`sign_transaction` / `seal_transaction`** (`TransactionSealSigner`)
   — produces the `TransactionSealSignature` over
   `unsealed.to_signing_message(())`. The seal closes off authorisations
   and finalises the `Transaction`.
3. **`sign_authorization_with_stealth` / `seal_transaction_with_stealth`**
   (`TransactionStealthKeySigner`) — same shape as 1 and 2, but the
   signing key is derived per-output via
   `kdfs::owner_stealth_dh_secret(network, account_secret, public_nonce)`.
   The recipient's wallet that holds the matching account secret can
   reconstruct that derived secret and spend the output. Outside
   observers see only ephemeral keys.

There is also `EphemeralKeySigner` (`transaction/ephemeral_signer.rs`):
generates a one-shot random `RistrettoSecretKey` and seals with it. Used
when a stealth transaction has *no* required signers (purely producing
new outputs to recipients) — `WalletStealthAuthorizer` falls back to it
in `wallet/stealth.rs:80-85`.

## ElGamal viewable-balance decryption

When a resource has a view key configured on-chain, every UTXO created
for that resource must include an ElGamal-encrypted commitment to the
amount. The view-secret holder can recover the amount by brute-force
search over a bounded value range, accelerated by a precomputed lookup
table.

Public surface:

```rust
// crates/wallet/ootle-rs/src/provider/balance.rs
fn decrypt_stealth_utxo_values<TLookup: ValueLookupTable>(
    &self, view_secret_key: &RistrettoSecretKey,
    utxo_substates: &HashMap<SubstateId, Substate>,
    value_range: RangeInclusive<u64>, lookup: &mut TLookup)
    -> ProviderResult<HashMap<UtxoAddress, u64>>;

async fn get_utxo_value<TLookup: ValueLookupTable>(...) -> ProviderResult<Option<u64>>;
```

The `ValueLookupTable` trait comes from
`tari_ootle_common_types::engine_types::crypto`. Two practical impls
exist upstream:

- `GenerateValueLookup` — generates commitments on the fly. Slow (used
  in tests/examples).
- `MMapValueLookup` — gated behind the `mmap-value-lookup` Cargo
  feature; reads a precomputed lookup binary. `cargo install
  tari_value_lookup_generator` creates the file.

A Python port that wants a fast view-key wallet will need to either bind
the upstream Rust lookup table or reimplement the brute-force loop with
NumPy/`gmpy2` over precomputed tables.

## Where keys are *not* derived

`ootle-rs` does **no** HD derivation, no BIP-32, no mnemonic handling.
`OotleSecretKey::random` makes two independent uniformly random Ristretto
secrets and that is that. Mnemonic seed handling, key-encrypted-storage,
and hardware-wallet integration are all out of scope for this crate —
they are the concern of a higher-level wallet application that builds
on top.
