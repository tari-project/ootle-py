# 05 — Traits & Extension Points

`ootle-rs` is built around small traits with one or two concrete impls
each. A Python port will most likely model these as `Protocol`s or
`abc.ABC`s, so the trait map matters.

## The provider abstraction

```rust
// crates/wallet/ootle-rs/src/provider/traits.rs
pub trait Provider {
    type Client;
    fn network(&self) -> Network;
    fn weak_client(&self) -> Weak<Self::Client>;
    fn client_upgrade(&mut self) -> Option<Arc<Self::Client>>;     // default impl
    fn default_signer_address(&self) -> &Address;

    fn resolve_input_want_list(&self, transaction: UnsignedTransaction,
        want_list: &HashSet<WantInput>)
        -> impl Future<Output = ProviderResult<UnsignedTransaction>> + Send;

    fn fetch_substates<I: IntoIterator<Item = SubstateId> + Send>(&self, ids: I)
        -> impl Future<Output = ProviderResult<HashMap<SubstateId, Substate>>> + Send;
}

pub trait WalletProvider: Provider {
    type Wallet;
    fn wallet(&self) -> &Self::Wallet;
    fn wallet_mut(&mut self) -> &mut Self::Wallet;
}
```

Concrete impl: `IndexerProvider<Wallet>` (`provider/indexer.rs:168`),
`Client = IndexerRestApiClient`. The trait uses `impl Future` (not
`async-trait`) — **not dyn-compatible**. Builder code uses generic bounds
(`P: Provider`, `P: WalletProvider<Wallet = OotleWallet>`) instead of
trait objects. A Python `Protocol` has no such constraint.

## The wallet abstraction

```rust
// crates/wallet/ootle-rs/src/wallet/traits.rs
pub trait NetworkWallet {
    fn default_address(&self) -> &Address;
    fn sign_transaction(&self, unsigned: UnsignedTransaction)
        -> impl Future<Output = WalletResult<Transaction>> + Send;
}

// Composite — auto-implemented for any T meeting all four bounds.
pub trait WalletKeyProvider:
    TransactionSigner + TransactionStealthKeySigner
    + StealthOutputStatementFactory + InputDecryptor {}
```

`NetworkWallet` is what the provider actually holds and what builders take.
`WalletKeyProvider` is the union of capabilities a per-key signer needs
to be registered into an `OotleWallet`. The blanket impl
(`wallet/traits.rs:27-28`) means anyone implementing the four constituent
traits *automatically* qualifies — there is no opt-in marker.

Concrete impls: `OotleWallet` is `NetworkWallet` and `TransactionSealSigner`
(`wallet/ootle.rs:174-200`); `LocalKeyProvider<C>` (alias `PrivateKeyProvider`)
satisfies `WalletKeyProvider` via the four traits below
(`key_provider/local/generic_impls.rs`). `WalletStealthAuthorizer` is a
`NetworkWallet` and `TransactionSealSigner` adapter sitting on top of
`OotleWallet` (`wallet/stealth.rs:64-127`).

## Signing traits

```rust
// crates/wallet/ootle-rs/src/transaction/signer.rs
#[async_trait]
pub trait TransactionSigner {
    fn address(&self) -> &Address;
    async fn sign_transaction(&self, message: &UnsealedTransaction)
        -> signer::Result<TransactionSealSignature>;
    async fn sign_authorization(&self, seal_signer: &RistrettoPublicKeyBytes,
        tx: &UnsignedTransaction) -> signer::Result<TransactionAuthorization>;
}

#[async_trait]
pub trait TransactionSealSigner {
    async fn seal_transaction(&self, transaction: UnsealedTransaction)
        -> signer::Result<Transaction>;
}

#[async_trait]
pub trait TransactionStealthKeySigner {
    async fn sign_authorization_with_stealth(&self,
        public_nonce: &RistrettoPublicKey, seal_signer: &RistrettoPublicKeyBytes,
        tx: &UnsignedTransaction) -> signer::Result<TransactionAuthorization>;
    async fn seal_transaction_with_stealth(&self,
        public_nonce: &RistrettoPublicKey, message: &UnsealedTransaction)
        -> signer::Result<TransactionSealSignature>;
}
```

The note in the source (`signer.rs:11`) says `async_trait` is needed
because `impl Future` is not dyn-compatible, and these traits *are* used
through `&dyn` in `TransactionRequest::build`. A Python port using
`Protocol` again has no such concern — async methods just work.

Concrete impls (all in `key_provider/local/generic_impls.rs`):
- `LocalKeyProvider<C>: TransactionSigner` where `C: PrehashSigner<…>`
- `LocalKeyProvider<C>: TransactionStealthKeySigner` where
  `C: StealthKeyPrehashSigner<…>`

Plus `OotleWallet: TransactionSealSigner` (`wallet/ootle.rs:191-200`) and
`WalletStealthAuthorizer<'_, OotleWallet>: TransactionSealSigner +
NetworkWallet` (`wallet/stealth.rs:64-127`).

## Stealth traits

```rust
// crates/wallet/ootle-rs/src/stealth/traits.rs
#[async_trait] pub trait StealthOutputStatementFactory {
    async fn generate_outputs_statement(&self, specs: Vec<Output>, revealed: Amount)
        -> StealthResult<(StealthOutputsStatement, RistrettoSecretKey)>;
}
#[async_trait] pub trait InputDecryptor {
    async fn decrypt_input_data(&self, commitment, input: &OutputBody, skip_memo: bool)
        -> StealthResult<DecryptedData>;
}
pub trait StealthSigner { type Signature;
    fn sign_with_stealth_key(&self, pk: &RistrettoPublicKey) -> Result<Self::Signature, String>;
}
pub trait StealthProvider: StealthOutputStatementFactory + InputDecryptor {}   // blanket
```

Impls in `key_provider/local/generic_impls.rs`:
`LocalKeyProvider<C: OutputMaskProvider>: StealthOutputStatementFactory`,
`LocalKeyProvider<C: HasViewOnlyKeySecret>: InputDecryptor`. `StealthSigner`
is unused inside the crate — it's an external hook.

## Key-provider traits

```rust
// crates/wallet/ootle-rs/src/key_provider/traits.rs
#[async_trait] pub trait OutputMaskProvider {
    async fn next_mask(&self) -> Result<RistrettoSecretKey>;
}
#[async_trait] pub trait DiffieHellmanKdfKeyProvider<H> {
    async fn create_kdf_dh_key(&self, hasher: H, public_key: &RistrettoPublicKey)
        -> Result<RistrettoSecretKey>;
}

// crates/wallet/ootle-rs/src/keys/traits.rs
pub trait HasViewOnlyKeySecret {
    fn view_only_secret(&self) -> &RistrettoSecretKey;
}

// crates/wallet/ootle-rs/src/signer/stealth_key.rs
pub trait StealthKeyPrehashSigner<S> {
    fn sign_prehash_with_stealth_key(&self, public_key: &RistrettoPublicKey,
        prehash: &[u8]) -> impl Future<Output = signer::Result<S>> + Send;
}
```

`OotleSecretKey` (`keys/secret.rs:25`) implements all four: `OutputMaskProvider`
(random masks), `HasViewOnlyKeySecret` (return inner), `PrehashSigner`
(non-stealth Schnorr), `StealthKeyPrehashSigner` (Schnorr over a derived
DH secret). This is the pivot point: every stealth/non-stealth, signing/
KDF capability is delivered by this one type.

## Builder traits

```rust
// crates/wallet/ootle-rs/src/builtin_templates/traits.rs
pub trait UnsignedTransactionBuilder {
    fn default_signer_address(&self) -> &Address;
    fn add_input<S: Into<SubstateRequirement>>(self, id: S) -> Self;
    fn prepare(self) -> impl Future<Output = Result<UnsignedTransaction, ProviderError>>;
}
```

Implemented by `AccountInvokeBuilder`, `FaucetInvokeBuilder`,
`ComponentInvokeBuilder`. Macro-generated wrappers proxy to
`ComponentInvokeBuilder`. The richer `OotleInvoke`
(`builtin_templates/component.rs:48`) — implemented only by
`ComponentInvokeBuilder` — adds want-input control, workspace plumbing,
`chain` for cross-builder composition, and the `then` escape hatch to
`TransactionBuilder`.

## Trait→impl summary

| Trait | Concrete impls |
|---|---|
| `Provider` / `WalletProvider`           | `IndexerProvider<W>` |
| `NetworkWallet`                         | `OotleWallet`, `WalletStealthAuthorizer<'_, OotleWallet>` |
| `WalletKeyProvider` (blanket)           | any `LocalKeyProvider<C: …>` meeting all four sub-traits |
| `TransactionSigner`                     | `LocalKeyProvider<C: PrehashSigner<…>>` |
| `TransactionSealSigner`                 | `OotleWallet`, `WalletStealthAuthorizer` |
| `TransactionStealthKeySigner`           | `LocalKeyProvider<C: StealthKeyPrehashSigner<…>>` |
| `StealthOutputStatementFactory`         | `LocalKeyProvider<C: OutputMaskProvider>` |
| `InputDecryptor`                        | `LocalKeyProvider<C: HasViewOnlyKeySecret>` |
| `DiffieHellmanKdfKeyProvider<H>`        | `LocalKeyProvider<C: HasViewOnlyKeySecret>` |
| `OutputMaskProvider`, `HasViewOnlyKeySecret`, `StealthKeyPrehashSigner<S>` | `OotleSecretKey` |
| `UnsignedTransactionBuilder`            | `AccountInvokeBuilder`, `FaucetInvokeBuilder`, `ComponentInvokeBuilder` |
| `OotleInvoke`, `IntoBuildParts`         | `ComponentInvokeBuilder` |
