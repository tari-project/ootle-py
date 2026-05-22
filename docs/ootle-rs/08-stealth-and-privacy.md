# 08 — Stealth & Privacy

Stealth transfers are the Tari-native confidential-asset feature. They
let a sender transmit value to a recipient without exposing the
recipient's public address on chain, without revealing transferred
amounts, and (with view keys) while still allowing auditors to read
balances on demand. This is the most Tari-specific subsystem in
`ootle-rs` and also the most complex — it touches every layer.

## What "stealth" means in `ootle-rs`

A stealth transfer is *a transaction that:*

1. Spends one or more **stealth UTXOs** (`StealthInput`) where the
   amount and recipient public key are both hidden inside Pedersen
   commitments + AEAD-encrypted blobs.
2. Produces zero or more **stealth outputs** (`StealthUnspentOutput`)
   each addressed to a derived stealth public key — the recipient's
   wallet can detect and decrypt their own outputs from chain data
   using their view-only secret.
3. Carries a **balance proof** signature proving inputs == outputs
   without revealing individual amounts (skipped when the transfer
   only creates outputs from revealed inputs and uses no stealth
   inputs).
4. Carries a **range proof** (Bulletproof) over output amounts so
   that `0 ≤ amount < 2^64` is enforced by validators.
5. May also include **revealed** inputs (e.g. from a previous bucket)
   and/or **revealed** outputs (e.g. to pay validator fees in plain
   TARI).

## Two-phase orchestration

A stealth transfer is built in *two* steps:

1. **`prepare()`** assembles the cryptographic statement
   (`StealthTransferStatement`) and computes the
   `SignatureRequirements` describing which keys must sign.
2. **Authorization & sealing** — `WalletStealthAuthorizer` walks the
   `SignatureRequirements`, asks the wallet to produce per-signer
   stealth-key authorisations, and then seals the transaction with
   the appropriate seal signer (account key, stealth key, or
   ephemeral key — depending on what the requirements say).

This split exists because the transaction body needs the cryptographic
statement *baked in* before any signature can commit to it. Sealing
must come last.

## The builder

```rust
// crates/wallet/ootle-rs/src/stealth/builder.rs
pub struct StealthTransfer<'a, P> { provider: &'a P, spec: StealthTransferSpec }

impl<'a, P: WalletProvider<Wallet = OotleWallet>> StealthTransfer<'a, P> {
    pub fn new(resource: ResourceAddress, provider: &'a P) -> Self;

    pub fn spend_revealed_input<A: Into<Amount>>(self, amount: A) -> Self;
    pub fn spend_stealth_input<I: Into<StealthInput>>(self, owner: Address, input: I) -> Self;
    pub fn to_revealed_output<A: Into<Amount>>(self, amount: A) -> Self;
    pub fn to_stealth_output(self, output: Output) -> Self;

    pub async fn prepare(self) -> WalletResult<(StealthTransferStatement, SignatureRequirements)>;
}
```

`prepare()` is the heavy step (`builder.rs:50-203`). It:

1. Maps each `StealthInput` to a `SubstateId(UtxoAddress)` and fetches
   them via `provider.fetch_substates()`.
2. For every input UTXO: validates it's not frozen/burnt, decrypts the
   AEAD-encrypted output body via `wallet.decrypt_input_data()` to
   recover its mask, and records the spender's address +
   `RistrettoPublicKey` nonce as a `StealthSignerRequirement`.
3. Aggregates input masks (`agg_input_mask`).
4. Generates the outputs statement (range proof + ElGamal viewable
   balances) via `wallet.generate_outputs_statement(specs, revealed)`,
   producing an aggregated output mask as a side product.
5. Builds the `StealthInputsStatement` from the input collection.
6. If both sides are non-empty, signs an aggregate balance proof:
   `generate_stealth_balance_proof_signature(agg_input_mask,
   agg_output_mask, inputs_statement, outputs_statement)`. Verifies
   it locally before returning.
7. Validates the whole transfer with
   `tari_ootle_common_types::engine_types::stealth::validate_transfer`.
8. Picks one of two `SignatureRequirements` constructors:
   - `new_must_sign_with_account_key(...)` if any revealed input is
     positive — the sender must prove account-key ownership of those
     funds.
   - `new_opt_with_seal_signer(...)` otherwise — pure stealth path.

The pivotal detail: `prepare()` does not yet build a transaction. It
returns the **statement to embed** and the **signers required** to
authorise it. The caller is responsible for embedding the statement in
a `TransactionBuilder` (typically via `IFaucet::take_faucet_funds_stealth`
or `Transaction::builder().with_fee_instructions_builder(|b|
b.stealth_transfer(...))`).

## The stealth authorizer

```rust
// crates/wallet/ootle-rs/src/wallet/stealth.rs
pub struct WalletStealthAuthorizer<'a, W: ?Sized> {
    wallet: &'a W,
    required_signatures: SignatureRequirements,
}

impl WalletStealthAuthorizer<'_, OotleWallet> {
    pub async fn create_authorizations(&self, unsigned: &UnsignedTransaction)
        -> signer::Result<Vec<TransactionAuthorization>>;
}

// Also impls TransactionSealSigner and NetworkWallet.
```

`create_authorizations` (`stealth.rs:32-61`):

1. Determines the **seal signer's public key**: if
   `must_sign_with_account_key`, use the wallet's default account public
   key. Otherwise use the explicit `seal_signer` from the requirements.
2. For every `other_signer`, asks the wallet's matching key provider
   for a stealth-key authorisation:
   `wallet.authorize_transaction_with_stealth_key(req.signer(),
   req.public_nonce(), seal_signer, unsigned)`
   (see `wallet/ootle.rs:140-154`).
3. Returns the `Vec<TransactionAuthorization>`.

The `TransactionSealSigner` impl (`stealth.rs:64-92`) decides which key
seals the final transaction in three branches:

- **`Some(Some(seal_signer))`** — seal with a stealth key (account-key
  signing not required, and either an explicit seal signer is set or
  there's a fallback first-required-signer).
- **`Some(None)`** — no inputs to spend, so an ephemeral key seals
  (privacy-preserving; the sealing key is thrown away).
- **`None`** — `must_sign_with_account_key` is true, so seal with the
  wallet's default key (`OotleWallet::seal_transaction`).

## How a caller uses it (skeleton)

```rust
let (statement, sig_reqs) = StealthTransfer::new(TARI_TOKEN, &provider)
    .spend_stealth_input(my_addr, prev_input.commitment())
    .to_revealed_output(500u64)
    .to_stealth_output(Output::new(recipient, TARI_TOKEN, NonZeroU64::new(8 * TARI).unwrap()))
    .prepare()
    .await?;

let unsigned_tx = Transaction::builder(network)
    .with_fee_instructions_builder(|b| {
        b.stealth_transfer(TARI_TOKEN, statement)
         .put_last_instruction_output_on_workspace("fees")
         .pay_fee_from_bucket("fees")
    })
    .add_input(TARI_TOKEN)
    .add_input(UtxoAddress::new(TARI_TOKEN, prev_input.commitment().into()))
    .build_unsigned();

let authorizer = provider.wallet().stealth_authorizer(sig_reqs);
let auths      = authorizer.create_authorizations(&unsigned_tx).await?;
let tx         = TransactionRequest::default()
    .with_transaction(unsigned_tx)
    .with_authorizations(auths)
    .build(&authorizer)
    .await?;

let pending = provider.send_transaction(tx).await?;
```

## The faucet stealth path

`IFaucet::take_faucet_funds_stealth(transfer, pay_revealed_amount_as_fees)`
(`builtin_templates/faucet.rs:91-142`) is a special builder that takes
an *already-prepared* `StealthTransferStatement` and wires it through
the faucet template's `take_confidential` instruction. It also adds
each input's commitment to the want-list as a `WantInput::SpecificSubstate`
so the input resolver fetches them.

This is the canonical "free starter funds → stealth UTXO" flow used by
the `examples/stealth_transfer.rs` walkthrough.

## What this means for a Python port

- The math (Bulletproofs, ElGamal verifiable balances, balance-proof
  signatures, AEAD-encrypted output bodies) lives upstream in
  `tari_ootle_wallet_crypto`. A Python port has three options here:
  (a) PyO3 bindings to the Rust crate, (b) a full reimplementation
  (large effort), (c) deliberately ship without stealth in v1.
- The orchestration shape (`prepare → authorize → seal`) is regular
  Python code. The state machine in `WalletStealthAuthorizer` is small
  and translates straightforwardly.
- The `SignatureRequirements` invariants (see `04` and the unit tests
  in `spec.rs:179-244`) are worth porting verbatim — they are the
  "is this transaction shape coherent?" oracle.
