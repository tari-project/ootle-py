# 11 — Examples Walkthrough

The `examples/` directory has four runnable programs. They are the best
catalogue of "what is `ootle-rs` for?" — each pins down a different
usage pattern.

All examples are `#[tokio::main]`, target `Network::LocalNet` by default,
and use `default_indexer_url(NETWORK)` to discover the indexer.

## `examples/balance_query.rs` (139 lines)

Read-only flow. Builds an `IndexerProvider<NoWallet>` (no wallet needed)
and exercises three balance APIs.

```rust
let provider = ProviderBuilder::new().connect(indexer_api_url).await?;

// 1. Single resource
let tari = provider.get_account_balance(account_component, TARI_TOKEN).await?;

// 2. All resources for an account
for (resource, balance) in provider.get_account_balances(account_component).await? {
    println!("{resource}: {balance}");
}

// 3. ElGamal-decrypt a stealth UTXO using a view secret key
let value = provider
    .get_utxo_value(&view_secret_key, utxo_address, 0..=20_000_000, &mut GenerateValueLookup)
    .await?;
```

Notable: this is the only example that imports nothing from `wallet`,
`signer`, or `transaction` — proves a read-only client is a first-class
shape. The example explicitly warns about `GenerateValueLookup` being
slow and points users to the `mmap-value-lookup` feature for production.

A Python equivalent should preserve the read-only-provider construction
shape; balance lookup needs no signing.

## `examples/fungible_transfer.rs` (196 lines)

The "happy path" non-stealth public transfer flow.

Highlights:

1. Two random `PrivateKeyProvider`s registered into one `OotleWallet`
   via `wallet.register_key_provider(another_signer)`. Demonstrates the
   multi-signer model.
2. **Faucet step** — `IFaucet::new(&provider).take_faucet_funds(10*TARI)
   .pay_fee(500u64).prepare()` → `TransactionRequest` →
   `provider.send_transaction(tx)`.
3. **Transfer step** — `IAccount::new(&provider).pay_fee(1000u64)
   .public_transfer(recipient1, TARI_TOKEN, 2*TARI)
   .public_transfer(recipient2, TARI_TOKEN, 1*TARI)` (multiple recipients
   in one transaction).
4. **Dry run** — `provider.sign_and_send_dry_run(unsigned_tx.clone())
   .await?` produces `ExecuteResult` containing the estimated fee
   (`result.finalize.fee_receipt.total_fees_charged()`). The example
   then *also* sends the real transaction.
5. **Co-signing** — explicitly authorises with the *second* signer:
   `provider.wallet().authorize_transaction(&another_address,
   &unsigned_tx).await?` and adds the result via
   `TransactionRequest::default().add_authorization(authorization)`.
   This shows how multi-signer transactions work without using
   `WalletStealthAuthorizer`.
6. **Receipt inspection** — `pending_tx.get_receipt().await?` and a
   pretty-printer over `receipt.events`, `receipt.logs`,
   `receipt.fee_receipt`.

This is the canonical "send TARI" example. Almost every line maps to
something a wallet UI does.

## `examples/stealth_transfer.rs` (216 lines)

The advanced privacy flow. Same shape as `fungible_transfer` but every
step uses the stealth subsystem.

Two transactions:

1. **Stealth faucet** — `StealthTransfer::new(TARI_TOKEN, &provider)
   .spend_revealed_input(10*TARI + 1000) .to_revealed_output(500)
   .to_stealth_output(Output::new(sender, ..., NonZeroU64::new(...)))
   .prepare().await?` → `IFaucet::take_faucet_funds_stealth(transfer,
   true)` → seal via `provider.wallet().stealth_authorizer(required_signers)`.
2. **Stealth transfer to recipient** — spends the stealth UTXO created
   above (`spend_stealth_input(sender_address, input.commitment())`),
   produces two outputs (8 TARI to recipient with an encrypted memo,
   2 TARI back to self as change), and pays fees from a 500-µTARI
   revealed output. The unsigned transaction is built using the raw
   `Transaction::builder(network).with_fee_instructions_builder(...)`
   path — the *only* example to do so, demonstrating the escape hatch
   for transactions that don't fit `IFaucet`/`IAccount`/`IComponent`.
3. **Dry-run with explicit signer** — calls
   `provider.sign_and_send_dry_run_with(&authorizer, unsigned_tx.clone())`
   passing the stealth authorizer as the signer (because
   `OotleWallet::sign_transaction` would default to the account-key
   path).
4. **Authorize then build** —
   `let authorizations = authorizer.create_authorizations(&unsigned_tx).await?;`
   followed by
   `TransactionRequest::default().with_transaction(...).with_authorizations(authorizations)
   .build(&authorizer)`.

This example is the basis for the trace in
[`09-end-to-end-flow.md`](09-end-to-end-flow.md).

## `examples/template_invoke.rs` (273 lines)

The largest example. Demonstrates the macro-generated typed-template
DSL.

Step 1: declare an interface for a deployed template:

```rust
ootle_template! {
    template StableCoin {
        fn instantiate(view_key: RistrettoPublicKeyBytes);   // template fn (no self)
        fn increase_supply(&mut self, amount: Amount);       // component method
        fn deposit(&mut self, bucket: Bucket);
        fn freeze_utxos(&self, utxos: Vec<UtxoId>);
        // ...
    }
}
```

Step 2: use the two interface markers:
- `StableCoin::for_template(template_addr, &provider)` — only the
  no-`self` functions (e.g. constructor / `instantiate`).
- `StableCoin::for_component(component_addr, &provider)` — only the
  `&self`/`&mut self` methods.

Step 3: chain calls in transactions, with workspace piping:

```rust
let unsigned_tx = coin
    .withdraw(Amount::new(100_000))
    .put_last_instruction_output_on_workspace("bucket")
    .deposit(workspace!("bucket"))                         // workspace! → NamedArg
    .then(|b| b.call_method(c, "increase_supply", args![42u64]))
    .pay_fee(1000u64)
    .prepare().await?;
```

Step 4: the "untyped" fallback path:

```rust
IComponent::new(&provider)
    .call_method(component, "decrease_supply", args![Amount::new(500_000)])
    .pay_fee(1000u64)
    .prepare().await?;
```

Notable: this example uses `tari_ootle_transaction::workspace!` and
`tari_ootle_transaction::args!` directly — they are wire-level macros
that the template DSL builds on top of.

A Python port has no compile-time typed-template generation, but a
runtime equivalent (e.g. a `class StableCoin: ...` generated from a
JSON manifest, or a thin `.method(name, args)` proxy) maps the same
mechanism into idiomatic Python.

## What the examples *don't* show

- No example demonstrates `provider.watch_events(filter)` (the SSE
  template-event subscription). It is part of the public API — see
  `03-public-api.md` — but consumers are expected to consume it via
  `into_stream()` directly.
- No example uses `OotleWallet::set_default_signer` to switch the
  default-signing key after construction.
- No example connects to a remote network with HTTPS / authentication
  (because there is none — see `06-transport-and-serialization.md`).

Together the four examples cover roughly 90% of the public API. A
Python-port test plan that runs equivalents of these four examples
against a Localnet indexer is a strong fidelity oracle.
