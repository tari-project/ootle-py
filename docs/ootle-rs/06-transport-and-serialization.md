# 06 — Transport & Serialization

## The transport: `tari_indexer_client`

`ootle-rs` does not implement HTTP itself. All wire I/O is delegated to the
workspace crate `tari_indexer_client`, specifically its
`IndexerRestApiClient` (REST) and its SSE helpers. Connection setup is a
single call:

```rust
// crates/wallet/ootle-rs/src/provider/builder.rs:42-44
let client = tari_indexer_client::connect_rest(url.as_ref())?;
IndexerProvider::new(client, self.wallet, self.network)
```

The client is held inside `Arc<IndexerRestApiClient>` so that watcher tasks
and `PendingTransaction` handles can take a `Weak<_>` and detect drops
(`provider/indexer.rs:46-52`, `tx_watcher.rs:238`,
`event_watcher.rs:52-58`).

There is **no auth, no JSON-RPC, no gRPC, no WebSocket**. Just REST + SSE
over HTTP.

## Endpoints in use

These are the only methods of `IndexerRestApiClient` that `ootle-rs`
calls. Each maps to a single REST route in the indexer; the route names
below are inferred from the methods (the indexer crate is the
authoritative source).

| Operation                                | `IndexerRestApiClient` method                                          | Used at                                                             |
|------------------------------------------|------------------------------------------------------------------------|---------------------------------------------------------------------|
| Network info / current epoch             | `get_network_info()`                                                   | `provider/indexer.rs:76,89`                                         |
| Fetch a single substate                  | `get_substate(&id, GetSubstateRequest::default())`                     | `provider/indexer.rs:81-86, 102-108`                                |
| Fetch many substates                     | `fetch_substates(GetSubstatesRequest{requests, cached_only:false})`    | `provider/indexer.rs:204-212`, `balance.rs:161-168`, `input_resolver.rs:349-356` |
| Submit a transaction                     | `submit_transaction(SubmitTransactionRequest{transaction: envelope})`  | `provider/indexer.rs:151-153`                                       |
| Submit a dry-run transaction             | `submit_transaction_dry_run(SubmitTransactionRequest{...})`            | `provider/indexer.rs:128-134`                                       |
| Get transaction result                   | `get_transaction_result(GetTransactionResultRequest{transaction_id})`  | `tx_watcher.rs:373-378`                                             |
| Get transaction receipt                  | `get_transaction_receipt(receipt_address)`                             | `tx_watcher.rs:382-389`                                             |
| Subscribe to all SSE events              | `sse_events()`                                                         | `tx_stream.rs:130-138` (paused stream feeding `TransactionWatcher`) |
| Subscribe to filtered template events    | `sse_transaction_events(StreamTransactionEventsRequest{...})`          | `event_watcher.rs:73-80` (the public `watch_events`)                |

A few non-obvious points:

- **Two separate SSE channels.** The transaction-finality watcher and the
  user-facing `watch_events()` open independent streams — they are not
  multiplexed.
- **Implicit batch limit.** `GetSubstatesRequest::requests` is a bounded
  collection. The input resolver chunks queries to 20 per request
  (`input_resolver.rs:347`), and `fetch_substates` errors with "Too many
  substates requested in single request" if exceeded
  (`provider/indexer.rs:209`).
- **`cached_only: false` everywhere.** No code path opts into the
  indexer's cache-only mode.

## Wire formats

There are two on the wire and one on the read-back path.

### Borsh: the transaction envelope

```rust
// crates/wallet/ootle-rs/src/provider/indexer.rs:128-156
let envelope = TransactionEnvelope::encode(transaction)?;
self.client.submit_transaction(SubmitTransactionRequest { transaction: envelope }).await
```

`TransactionEnvelope::encode` (from `tari_ootle_transaction`, backed by
`tari_bor`) produces a Borsh-encoded byte blob. The envelope carries
versioning information; the indexer decodes the envelope before relaying
to validator nodes. Encoding errors surface as
`ProviderError::TransactionEncodeError(tari_bor::BorError)`.

### JSON: REST request/response bodies

`IndexerRestApiClient` serialises request structs (`SubmitTransactionRequest`,
`GetSubstateRequest`, `GetSubstatesRequest`, `GetTransactionResultRequest`,
`StreamTransactionEventsRequest`) and deserialises response types via
`serde_json`. The `transaction` field of the submit-transaction body is the
**Borsh-encoded envelope** wrapped inside the JSON body (so the wire
encoding is JSON-with-binary-blob, not pure binary).

### SSE event payloads

Both SSE streams return `tari_indexer_client::sse::Event`:

```rust
struct sse::Event { event_type: String, data: String, ... }
```

The watcher discriminates on `event_type` and parses `data` as JSON
(`tx_watcher.rs:124-141`, `event_watcher.rs:83-95`). For
`TransactionFinalized` events, the body is `TransactionFinalizedEvent
{ transaction_id, outcome, … }`. For template events, it's
`TransactionEvent`.

## Wire types vs. domain types

`ootle-rs` does **not** define separate wire-format DTOs. Domain types
double as wire types:

- `Transaction`, `UnsignedTransaction`, `TransactionEnvelope` — defined
  in `tari_ootle_transaction`, used both at the API surface and on the
  wire (post-Borsh).
- `Substate`, `SubstateId`, `Epoch`, etc. — `tari_ootle_common_types`,
  same.
- Indexer-specific request/response shapes (`SubmitTransactionRequest`,
  `GetSubstatesRequest`, etc.) live in `tari_indexer_client::types`.

This means a Python port implementing the wire protocol from scratch
needs to reproduce the Borsh layout and the JSON shapes of those upstream
crates — they are the actual contract.

## The transaction watcher (background pump)

`provider/tx_watcher.rs` and `provider/tx_stream.rs` together implement a
pausable SSE consumer that turns `TransactionFinalized` events into
oneshot replies for `PendingTransaction` futures.

Lifecycle (`provider/indexer.rs:158-165`):
- Single instance per `IndexerProvider`, created lazily via `OnceLock` on
  first `send_transaction`.
- Starts paused; `Paused` (`tx_stream.rs:17-44`) is a `tokio::sync::watch`
  flag toggled when the pending request set is empty/non-empty.
- Run loop (`tx_watcher.rs:76-98`): `tokio::select!` over (a) request
  channel, (b) SSE event stream, (c) timeout sleep — reaping expired
  pending watches each tick.
- Inner stream (`tx_stream.rs:108-167`): unpauses, calls
  `client.sse_events()`, retries with a 5s back-off on stream errors.

A Python port would either (a) reproduce this with `asyncio.Queue` +
`asyncio.Event`, or (b) re-open the SSE stream per pending transaction
and accept the simpler-but-chattier model.

## Default URLs

```rust
// crates/wallet/ootle-rs/src/helpers.rs
pub fn default_indexer_url(network: Network) -> &'static str {
    match network {
        Network::LocalNet  => "http://localhost:12500",
        Network::Esmeralda => "http://217.182.93.35:50124",
        // MainNet / StageNet / NextNet / Igor — `unimplemented!`
    }
}
```

These hardcoded URLs are the only network-discovery mechanism in the
crate.
