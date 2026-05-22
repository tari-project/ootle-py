# 09 — End-to-End Flow: a Stealth Faucet Transfer

To make every layer concrete, this doc traces a single operation from
user code through the layers down to HTTP and back.

The trace is the **first** transaction in `examples/stealth_transfer.rs`
— claiming faucet funds *into a stealth UTXO* (so the funds land
encrypted on chain, not in a public component vault). It exercises the
provider, builder, stealth, signing, and transport layers.

```
examples/stealth_transfer.rs
└─ #[tokio::main] async fn main() {
   ├─ PrivateKeyProvider::random(NETWORK)              keys/secret.rs:46-54  (random Ristretto secrets)
   │     └─ OotleWallet::from(signer)                  wallet/ootle.rs:43-58 (default + register_key_provider)
   │
   ├─ ProviderBuilder::new()
   │     .wallet(wallet)
   │     .connect("http://localhost:12500")            provider/builder.rs:42-44
   │     └─ tari_indexer_client::connect_rest(url)            ──── HTTP CLIENT CREATED ────
   │     └─ IndexerProvider::new(client, wallet, network)
   │
   ├─ provider.get_network()                           provider/indexer.rs:76-79
   │     └─ client.get_network_info()                  ──── GET /network-info ────
   │
   ├─ StealthTransfer::new(TARI_TOKEN, &provider)      stealth/builder.rs:38-45
   │     .spend_revealed_input(10*TARI + 1000)
   │     .to_revealed_output(500u64)
   │     .to_stealth_output(Output::new(sender, TARI_TOKEN, ...))
   │     .prepare()                                    stealth/builder.rs:50-203
   │     │   ├─ provider.fetch_substates(input ids)    provider/indexer.rs:194-215
   │     │   │     └─ client.fetch_substates(GetSubstatesRequest{...}) ──── POST /substates ────
   │     │   │     (no inputs in this case → empty fetch returns early)
   │     │   ├─ wallet.decrypt_input_data(...)         wallet/ootle.rs:103-118
   │     │   │     └─ LocalKeyProvider::decrypt_input_data
   │     │   │           uses encrypted_data::unblind_output (tari_ootle_wallet_crypto)
   │     │   ├─ wallet.generate_outputs_statement(specs, revealed)
   │     │   │   └─ LocalKeyProvider::generate_outputs_statement
   │     │   │         create_output_witness × N        key_provider/local/generic_impls.rs:197-270
   │     │   │           (Pedersen commitment + AEAD encrypt + stealth pubkey derivation)
   │     │   │         tokio::task::spawn_blocking      ──── BLOCKING POOL: bulletproof ────
   │     │   │           generate_extended_bullet_proof (tari_ootle_wallet_crypto)
   │     │   ├─ generate_stealth_balance_proof_signature(...)
   │     │   ├─ validate_balance_proof_signature(...)  (sanity check)
   │     │   ├─ validate_transfer(...)                 (engine_types)
   │     │   └─ → (StealthTransferStatement, SignatureRequirements)
   │
   ├─ IFaucet::new(&provider)                          builtin_templates/faucet.rs:54-63
   │     .take_faucet_funds_stealth(transfer, true)    builtin_templates/faucet.rs:91-142
   │     │   (wires the faucet's `take_confidential` instruction; injects each
   │     │    UTXO commitment into want_list as WantInput::SpecificSubstate)
   │     .prepare()                                    builtin_templates/faucet.rs:41-51
   │     │   ├─ TransactionBuilder::build_unsigned()   (tari_ootle_transaction)
   │     │   ├─ provider.resolve_input_want_list(unsigned, want_list)
   │     │   │   └─ TransactionInputResolver::resolve_inputs
   │     │   │         provider/input_resolver.rs:56-91
   │     │   │         - chunked client.fetch_substates(20) until satisfied
   │     │   │         - mutates UnsignedTransaction.add_input(...) for each match
   │     │   │     ──── POST /substates (one or more passes) ────
   │     │   └─ → UnsignedTransaction with all inputs filled
   │
   ├─ provider.wallet().stealth_authorizer(required_signers)
   │     wallet/ootle.rs:136-138 → WalletStealthAuthorizer::new
   │
   ├─ TransactionRequest::default()
   │     .with_transaction(unsigned_tx)                types/transaction/request.rs:29-34
   │     .build(&authorizer)                           types/transaction/request.rs:55-60
   │     │   (no authorisations were added, so nothing to fold in)
   │     │   authorizer.seal_transaction(unsealed)      wallet/stealth.rs:64-92
   │     │   │   match required_signatures {
   │     │   │     // first faucet stealth tx has must_sign_with_account_key=true
   │     │   │     None branch:
   │     │   │       wallet.seal_transaction(unsealed)  wallet/ootle.rs:191-200
   │     │   │       └─ key_provider.sign_transaction(&tx)
   │     │   │             key_provider/local/generic_impls.rs:65-69
   │     │   │             OotleSecretKey::sign_prehash       keys/secret.rs:71-77
   │     │   │             RistrettoSchnorr::sign(account_secret, prehash, rng)
   │     │   │   }
   │     │   └─ Transaction (sealed)
   │     └─ → Transaction
   │
   ├─ provider.send_transaction(tx)                    provider/indexer.rs:138-156
   │     ├─ self.get_tx_watcher() (lazy spawn on first call) provider/indexer.rs:158-165
   │     │   spawns TransactionWatcher::run on tokio::task    tx_watcher.rs:61-65
   │     │   inner EventStream subscribes to client.sse_events() lazily  tx_stream.rs:130
   │     │   ──── SSE GET /events (paused until first request) ────
   │     ├─ envelope = TransactionEnvelope::encode(tx)?       (Borsh, via tari_bor)
   │     └─ client.submit_transaction(SubmitTransactionRequest{transaction: envelope})
   │           ──── POST /submit-transaction ────
   │     └─ PendingTransaction { tx_id, watcher, weak_client, default_timeout=32s }
   │
   ├─ pending_tx.watch()                               tx_watcher.rs:268-367
   │     ├─ watcher.watch_transaction(tx_id, 32s)
   │     │   sends TxWatchRequest on mpsc; receives PendingTransactionOutcome (Future)
   │     ├─ TransactionWatcher::run select! loop          tx_watcher.rs:76-98
   │     │   - on SSE TransactionFinalized event for our tx_id:
   │     │       reply.send(Ok(FinalizeOutcome::Commit | FeeIntentCommit))
   │     │   - on timeout: reap → Timeout error → caller's fallback queries
   │     │       client.get_transaction_result(GetTransactionResultRequest{tx_id})
   │     │       ──── POST /get-transaction-result ────
   │     │       → IndexerTransactionFinalizedResult::Finalized {...}
   │     └─ TransactionOutcome::Commit | OnlyFeeCommit(reason) | Reject(reason)
   │
   └─ pending_tx.get_receipt()                         tx_watcher.rs:399-470
         ├─ try_get_transaction_receipt
         │   client.get_transaction_receipt(tx_id.into_receipt_address())
         │   ──── GET /transaction-receipt ────
         └─ → TransactionReceipt { epoch, fee_receipt, events, logs, diff_summary, ... }
}
```

## What every layer touches in this single trace

| Layer (see `01-architecture.md`)        | What runs in this trace                                                  |
|------------------------------------------|--------------------------------------------------------------------------|
| 1 · User-facing API                      | `ProviderBuilder`, `IndexerProvider`, `TransactionRequest`, `OotleWallet`|
| 2 · Builtin templates / DSL              | `IFaucet::take_faucet_funds_stealth`                                     |
| 3 · Transaction & signing traits         | `TransactionSigner`, `TransactionSealSigner` (via `OotleWallet`)         |
| 4 · Stealth / privacy                    | `StealthTransfer`, `WalletStealthAuthorizer`, `SignatureRequirements`    |
| 5 · Cryptography & keys                  | `OotleSecretKey::sign_prehash`, `kdfs`, `StealthCryptoApi`, bulletproofs |
| 6 · Transport & serialization            | `IndexerRestApiClient`, `TransactionEnvelope::encode` (Borsh), SSE       |

## HTTP traffic for this single user action

Counting only the operations made *by* `ootle-rs` on the user's behalf
during this trace (not inside the indexer):

1. `GET /network-info` — `provider.get_network()`.
2. `POST /substates` — input-resolver fills required inputs (one or
   more passes; each carries up to 20 ids).
3. `POST /submit-transaction` — Borsh-encoded envelope inside JSON.
4. SSE `GET /events` — opened lazily at step 3, runs until paused
   again.
5. (Fallback) `POST /get-transaction-result` — only on SSE timeout or
   fee-only-commit recovery.
6. `GET /transaction-receipt` — `pending_tx.get_receipt()`.

A Python port that replicates this six-call shape will reproduce the
`ootle-rs` semantics for one stealth faucet claim end-to-end.

## Cross-reference quick map

- `ProviderBuilder::connect`: `provider/builder.rs:42-44`
- `IndexerProvider::send_transaction`: `provider/indexer.rs:138-156`
- `StealthTransfer::prepare`: `stealth/builder.rs:50-203`
- `WalletStealthAuthorizer::seal_transaction`: `wallet/stealth.rs:64-92`
- `OotleSecretKey::sign_prehash`: `keys/secret.rs:71-77`
- `TransactionInputResolver::resolve_inputs`: `provider/input_resolver.rs:56-91`
- `PendingTransaction::watch`: `provider/tx_watcher.rs:268-367`
