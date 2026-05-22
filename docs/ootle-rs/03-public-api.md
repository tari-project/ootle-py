# 03 — Public API Surface

This is the contract a consumer interacts with. All operations are async
unless flagged otherwise.

## Entry points

A consumer constructs three things in order:

```rust
// 1. Key provider (key_provider/local/private_key.rs)
pub type PrivateKeyProvider = LocalKeyProvider<OotleSecretKey>;
pub type PrivateKeySigner   = PrivateKeyProvider;         // alloy-style alias
PrivateKeyProvider::new(secret) | ::random(network) | ::random_with(network, rng)

// 2. Wallet (wallet/ootle.rs)
OotleWallet::new<S: WalletKeyProvider + 'static>(key: S) -> Self
OotleWallet::from(signer)                                 // also works
OotleWallet::register_key_provider(&mut self, key)        // multi-signer
OotleWallet::set_default_signer(&mut self, &Address) -> WalletResult<()>

// 3. Provider (provider/builder.rs)
ProviderBuilder::new()
    .with_network(network)                                // optional; else from wallet
    .wallet(wallet)
    .connect(url) -> Result<IndexerProvider<W>, IndexerRestClientError>
    .connect_with_transaction_timeout(url, timeout)
```

`OotleSecretKey` (`keys/secret.rs:25`) bundles two Ristretto secrets —
account (signing) + view-only (decrypts inbound stealth UTXOs). A builder
with no `.wallet(...)` call still connects — it gives a read-only
`IndexerProvider<NoWallet>` (used by `examples/balance_query.rs`).

## Top-level operations

Operations group into **network/state queries**, **balance queries**,
**transactions**, **dry-run**, **event watching**, and **wallet actions**.

### Network & state

```rust
// crates/wallet/ootle-rs/src/provider/indexer.rs:76-109
async fn get_network(&self) -> ProviderResult<Network>
async fn get_epoch(&self) -> ProviderResult<Epoch>
async fn fetch_substate<T: Into<SubstateId>>(&self, id: T) -> ProviderResult<Substate>
async fn get_substate<T: Into<SubstateId>>(&self, id: T) -> ProviderResult<Option<Substate>>
async fn fetch_substates<I: IntoIterator<Item = SubstateId>>(&self, ids: I)
    -> ProviderResult<HashMap<SubstateId, Substate>>      // via Provider trait
fn network(&self) -> Network                              // sync, cached at builder time
```

### Balances & UTXO decryption

```rust
// crates/wallet/ootle-rs/src/provider/balance.rs
async fn get_account_balance(&self, account: ComponentAddress, resource: ResourceAddress)
    -> ProviderResult<Amount>
async fn get_account_balances(&self, account: ComponentAddress)
    -> ProviderResult<HashMap<ResourceAddress, Amount>>

async fn get_utxo_value<TLookup: ValueLookupTable>(
    &self,
    view_secret_key: &RistrettoSecretKey,
    utxo_address: UtxoAddress,
    value_range: RangeInclusive<u64>,
    lookup: &mut TLookup,
) -> ProviderResult<Option<u64>>

fn decrypt_stealth_utxo_values<TLookup: ValueLookupTable>(
    &self,
    view_secret_key: &RistrettoSecretKey,
    utxo_substates: &HashMap<SubstateId, Substate>,
    value_range: RangeInclusive<u64>,
    lookup: &mut TLookup,
) -> ProviderResult<HashMap<UtxoAddress, u64>>           // sync — pure brute-force decrypt
```

`ValueLookupTable` comes from `tari_ootle_common_types::engine_types::crypto`.
The `mmap-value-lookup` Cargo feature wires in a memory-mapped lookup table
for production use; without it, `GenerateValueLookup` (slow, on-the-fly) is
the only option.

### Transactions

```rust
// crates/wallet/ootle-rs/src/provider/indexer.rs:113-156
async fn sign_and_send_dry_run(&self, unsigned: UnsignedTransaction)
    -> ProviderResult<ExecuteResult>                       // signs with default wallet
async fn sign_and_send_dry_run_with<W: NetworkWallet>(&self, wallet: &W, unsigned: UnsignedTransaction)
    -> ProviderResult<ExecuteResult>                       // explicit signer (e.g. WalletStealthAuthorizer)
async fn send_dry_run(&self, tx: Transaction) -> ProviderResult<ExecuteResult>
async fn send_transaction(&mut self, tx: Transaction) -> ProviderResult<PendingTransaction>
async fn send_transaction_envelope(&mut self, env: TransactionEnvelope)
    -> ProviderResult<PendingTransaction>
```

`PendingTransaction` is the handle a caller awaits:

```rust
// crates/wallet/ootle-rs/src/provider/tx_watcher.rs:236-471
fn tx_id(&self) -> TransactionId
fn with_timeout(self, timeout: Duration) -> Self
async fn register(&self, timeout: Duration) -> Result<PendingTransactionOutcome, _>
async fn watch(&self) -> Result<TransactionOutcome, PendingTransactionError>
async fn get_receipt(&self) -> Result<TransactionReceipt, PendingTransactionError>
```

`watch()` resolves to a `TransactionOutcome` (`Commit` / `OnlyFeeCommit` /
`Reject`); `get_receipt()` returns the full
`tari_ootle_common_types::engine_types::transaction_receipt::TransactionReceipt`
(epoch, fee receipt, events, logs, diff summary).

### Building unsigned transactions (the DSL surface)

```rust
// crates/wallet/ootle-rs/src/builtin_templates/account.rs
IAccount::new(&provider)
    .pay_fee(amount: impl Into<Amount>) -> Self
    .public_transfer(to: &Address, resource: ResourceAddress, amount) -> Self
    .publish_template(template: impl TryInto<TemplateBlob>) -> Self
    .add_input(SubstateRequirement) -> Self
    .prepare().await -> Result<UnsignedTransaction, ProviderError>

// crates/wallet/ootle-rs/src/builtin_templates/faucet.rs
IFaucet::new(&provider)
    .take_faucet_funds(amount)
    .take_max_faucet_funds()
    .take_faucet_funds_stealth(transfer: StealthTransferStatement, pay_fees_from_revealed: bool)
    .pay_fee(amount)
    .prepare().await -> Result<UnsignedTransaction, ProviderError>

// crates/wallet/ootle-rs/src/builtin_templates/component.rs
IComponent::new(&provider)
    .call_method(component, method_name, args![…])      // auto-discovers vaults
    .call_method_raw(component_or_workspace, method, args![…])
    .call_function(template_address, function_name, args![…])
    .pay_fee(amount)
    .want_vault_for(component, resource, required: bool)
    .want_substate(substate_id, required: bool)
    .want_all_vaults(component)
    .put_last_instruction_output_on_workspace(label)
    .chain(other_builder)                               // merges another builder's instructions
    .then(|raw_builder| ...)                            // escape hatch to TransactionBuilder
    .prepare().await
```

Plus the macro-generated typed wrappers via `ootle_template! { template
StableCoin { fn instantiate(...); fn increase_supply(&mut self, ...); } }`,
which produce `StableCoin::for_template(...)` and
`StableCoin::for_component(...)`.

### Authorisation & sealing (Layer 1 surface)

```rust
// crates/wallet/ootle-rs/src/types/transaction/request.rs
TransactionRequest::default()                              // == TransactionRequest<Initial>
    .with_transaction(unsigned: UnsignedTransaction) -> TransactionRequest<WithTx>
    .add_authorization(auth: TransactionAuthorization) -> Self
    .with_authorizations(iter)
    .build_unsealed() -> UnsealedTransaction
    .build(seal_signer: &dyn TransactionSealSigner) -> WalletResult<Transaction>

// crates/wallet/ootle-rs/src/wallet/ootle.rs
OotleWallet::authorize_transaction(address, &unsigned)
    -> WalletResult<TransactionAuthorization>
OotleWallet::stealth_authorizer(required_signatures: SignatureRequirements)
    -> WalletStealthAuthorizer<'_, Self>                  // implements TransactionSealSigner + NetworkWallet
OotleWallet::decrypt_input_data(commitment, input, skip_memo)
    -> WalletResult<DecryptedData>
OotleWallet::generate_outputs_statement(specs, revealed)
    -> WalletResult<(StealthOutputsStatement, RistrettoSecretKey)>
```

### Event watching

```rust
// crates/wallet/ootle-rs/src/provider/event_watcher.rs
fn watch_events(&self, filter: TransactionEventFilter) -> TransactionEventStream
TransactionEventStream::into_stream(self) -> impl Stream<Item = Result<TransactionEvent, EventWatcherError>>
```

`TransactionEventFilter { topic, substate_id, template_address }` — all
optional; an empty filter subscribes to everything.

This is **independent** from the per-transaction watcher used by
`PendingTransaction`. The latter watches finalization (`TransactionFinalized`
events); `watch_events()` watches template-emitted `Event` payloads.

## Async/sync summary & authentication

- All network ops are `async fn` (Tokio); pure crypto helpers
  (`decrypt_stealth_utxo_values`, key generation, building unsigned txs
  before `prepare`) and getters (`network()`, `tx_id()`) are sync.
- **No transport authentication.** Plain HTTP REST to the indexer; no JWT,
  session, header. All authorisation is on-chain via transaction signatures.
