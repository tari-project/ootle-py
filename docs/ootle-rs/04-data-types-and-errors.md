# 04 — Data Types & Errors

## Domain types

### Addresses

```rust
// crates/wallet/ootle-rs/src/types/address.rs
pub type Address = tari_ootle_address::OotleAddress;          // (network, view_pk, account_pk)
pub trait ToAccountAddress { fn to_account_address(&self) -> ComponentAddress; }
```

The on-network `ComponentAddress` for a user's account is **derived**, not
stored, via `derive_component_address_from_public_key(&ACCOUNT_TEMPLATE_ADDRESS,
addr.account_public_key())`. Re-exports: `pub type Signature =
TransactionSealSignature` (`types/mod.rs:14`); `Network` from
`tari_ootle_common_types`.

### Transaction request — type-state builder

```rust
// crates/wallet/ootle-rs/src/types/transaction/request.rs
pub struct Initial; pub struct WithTx(UnsignedTransaction);
pub struct TransactionRequest<State = Initial> {
    state: State, authorizations: Vec<TransactionAuthorization>,
}
```

`<Initial>` accepts authorisations only. `<WithTx>` has a transaction and
can be built unsealed (`build_unsealed`) or sealed via a
`&dyn TransactionSealSigner` (`build`). `build()` folds authorisations
into the unsigned tx's signature list and calls
`seal_signer.seal_transaction(unsealed)`.

### Pending transaction

```rust
// crates/wallet/ootle-rs/src/provider/tx_watcher.rs:236
pub struct PendingTransaction { watcher, client: Weak<...>, tx_id, default_timeout=32s }
pub struct PendingTransactionOutcome { tx_id, outcome_rx }   // impls Future
```

Two things to await: `register(timeout) -> PendingTransactionOutcome`
(itself a `Future`) for the raw `FinalizeOutcome`, or the higher-level
`watch() -> Result<TransactionOutcome, _>`, which folds in fee-only-commit
recovery and a query-fallback for SSE timeouts (`tx_watcher.rs:268-367`).

### Transaction outcome

```rust
// crates/wallet/ootle-rs/src/types/transaction/outcome.rs
pub enum TransactionOutcome {
    Commit,
    OnlyFeeCommit(RejectReason),               // tx accepted but only fees committed
    Reject(RejectReason),
}
```

Predicates: `is_commit`, `is_only_fee_commit`, `is_reject`,
`reject_reason() -> Option<&RejectReason>`.

### Vault balance

```rust
// crates/wallet/ootle-rs/src/provider/balance.rs:19-25
pub struct VaultBalance {
    pub vault_id: VaultId,
    pub resource_address: ResourceAddress,
    pub balance: Amount,
    pub locked_balance: Amount,
}
```

This struct is internal-ish: `get_account_balance(s)` collapse it into
`Amount` / `HashMap<ResourceAddress, Amount>` for the public surface.

### Want-input (input-resolver request shape)

```rust
// crates/wallet/ootle-rs/src/provider/want_input.rs
pub enum WantInput {
    VaultForResource { component_address, resource_address, required: bool },
    SpecificSubstate { substate_id: SubstateId, required: bool },
    AllComponentVaults { component_address },
}
```

`required` controls whether the resolver hard-errors on absence or
silently drops the want.

### Stealth output spec

```rust
// crates/wallet/ootle-rs/src/stealth/spec.rs:106
pub struct Output {
    destination: Address, amount: NonZeroU64, resource_address: ResourceAddress,
    resource_view_key: Option<RistrettoPublicKey>, memo: Option<Memo>,
    pay_to: PayTo,                  // StealthPublicKey | AccessRule
    utxo_tag: Option<UtxoTag>, minimum_value_promise: u64,
}
```

Fluent setters: `with_resource_view_key`, `with_memo`, `with_memo_message`,
`with_pay_to`, `with_utxo_tag`.

### Signature requirements

```rust
// crates/wallet/ootle-rs/src/stealth/spec.rs:13
pub struct StealthSignerRequirement { signer: Address, public_nonce: RistrettoPublicKey }
pub struct SignatureRequirements {
    required_signers: IndexSet<StealthSignerRequirement>,
    must_sign_with_account_key: bool,
    seal_signer: Option<StealthSignerRequirement>,
}
```

Two constructors capture the invariants —
`new_must_sign_with_account_key(required)` (wallet account key must sign;
no seal signer) and `new_opt_with_seal_signer(required, seal_signer)`
(account key optional; ephemeral key seals if no signers).
`seal_signer()` / `other_signers()` partition for the authorizer; unit
tests in `spec.rs:179-244` enforce the invariants.

### Transaction event filter

```rust
// crates/wallet/ootle-rs/src/provider/event_watcher.rs:19
pub struct TransactionEventFilter { topic, substate_id, template_address }   // all Option<_>
```

### Misc external types you'll see

These come from upstream crates and are used directly by the public API:

- **`tari_ootle_common_types`**: `Substate`, `SubstateId`, `Epoch`,
  `Network`, `ExecuteResult`, `RejectReason`, `TransactionResult`,
  `TransactionReceipt`, `FinalizeOutcome`.
- **`tari_ootle_transaction`**: `Transaction`, `UnsignedTransaction`,
  `UnsealedTransaction`, `TransactionEnvelope`, `TransactionId`,
  `TransactionSignature`, `TransactionSealSignature`.
- **`tari_template_lib_types`**: `Amount`, `ComponentAddress`,
  `ResourceAddress`, `UtxoAddress`, `UtxoId`, `VaultId`, `TemplateAddress`,
  `EncryptedData`, `PedersenCommitmentBytes`, `RistrettoPublicKeyBytes`,
  `StealthOutputsStatement`, `StealthInputsStatement`,
  `StealthTransferStatement`, `StealthInput`, `StealthUnspentOutput`,
  `SpendCondition`, `UtxoTag`, `FunctionName`.

## Error taxonomy

All errors are `thiserror`-derived and module-scoped, with `#[from]`
conversions wiring them upward. The umbrella error returned by most
provider operations is `ProviderError`; transaction-watching surfaces a
separate `PendingTransactionError`.

```text
ProviderError                            (provider/error.rs)
├─ IndexerClientError(IndexerRestClientError)        # from tari_indexer_client
├─ TransactionEncodeError(tari_bor::BorError)
├─ TransactionInputResolutionError(TransactionInputResolverError)
├─ WalletError(WalletError)              # blanket From<E:Into<WalletError>>
└─ Other(String)

WalletError                              (wallet/error.rs)
├─ KeyProviderNotFound { address }
├─ SignerError(SignerError)              # signer/error.rs: InvalidCredentials | SignatureError | Other
├─ StealthProofError(StealthProofError)  # from tari_ootle_wallet_crypto
└─ StealthProviderError(StealthProviderError)

StealthProviderError                     (stealth/error.rs)
├─ StealthProofError, CryptoApiError, InvalidDestinationAddress
├─ RangeProofError, SpawnBlockingPanic, UnexpectedError
├─ InvalidInput(UtxoNotFound | UtxoIsFrozen | UtxoIsBurnt)
├─ UnbalancedTransfer { total_revealed_input, output_amount }
└─ DecryptionFailed { commitment, details }

PendingTransactionError                  (provider/tx_watcher.rs:179)
└─ ClientDropped | IndexerClientError | WatchAborted | ReceiptNotFound
   | TransactionRejected { tx_id, reason } | Timeout { tx_id }

TransactionInputResolverError            (provider/input_resolver.rs:26)
└─ IndexerClientError | IndexerClientDropped | IndexedValueError
   | RequiredSubstateNotFound | UnexpectedSubstateType

EventWatcherError                        (provider/event_watcher.rs:38)
└─ ClientDropped | IndexerClientError | StreamError | ParseError

EventStreamError                         (provider/tx_stream.rs:92)  # internal
KeyProviderError                         (key_provider/error.rs)     # Other(Box<dyn Error>)
```

`provider/error.rs:28-32` provides a blanket `impl<E: Into<WalletError>>
From<E> for ProviderError`, so wallet/signer/stealth errors composed via
`?` land as `ProviderError::WalletError(_)` automatically.

A Python port may collapse this taxonomy, but should preserve the
**Reject / OnlyFeeCommit / Timeout** distinctions on the transaction-watching
path — they carry different on-chain semantics.
