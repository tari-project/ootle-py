# `ootle-rs` — Architectural Reference

This directory documents the **Rust** crate `ootle-rs`, the upstream reference
client for the Tari L2 ("Ootle") network. The goal of these docs is to give a
self-contained architectural picture of `ootle-rs` *as it stands today*, so
that planning a Pythonic equivalent (`ootle-python`) does not require
re-reading the Rust source.

These docs describe what `ootle-rs` **is** — they do not yet propose what the
Python port should be.

## Source under documentation

`crates/wallet/ootle-rs/` in the upstream repo
`tari-ootle.martins`:

- ~5,724 LOC across 33 source files in `src/` plus 4 example programs
- Crate version `0.3.0`, dual-licensed Apache-2.0 / MIT
- File:line citations in these docs use paths relative to the repo root, e.g.
  `crates/wallet/ootle-rs/src/provider/indexer.rs:138`

## Stated design intent

From the upstream `README.md` (verbatim):

> `ootle.rs` is a pure Rust library designed to be the standard interface for
> interacting with Tari Ootle. It is architected to mirror the interface of
> [alloy-rs](https://github.com/alloy-rs/alloy), providing a seamless developer
> experience for those transitioning from Ethereum or generic blockchain
> development to the Tari ecosystem.

> ## Architecture
>
> ootle.rs follows the modular design of alloy:
>
> - **Core**: Defines the primitive types (Addresses, Signatures, Confidential
>   Commitments) specific to Tari.
> - **Transport**: Handles communication with Ootle Indexers and Validator
>   Nodes (VNs).
> - **Provider**: The high-level API for sending requests and managing state.
> - **Signer**: Abstractions for signing transactions (support for Ristretto
>   keys).

The four-layer alloy framing is the *aspirational* shape. The actual code in
the crate decomposes into a handful more layers — see
[`01-architecture.md`](01-architecture.md).

## Reading order

These files are ordered for a first-time reader. Each is also intended to
stand alone if you only need that piece.

1. [`01-architecture.md`](01-architecture.md) — layers, diagram, data flow.
2. [`02-modules.md`](02-modules.md) — module-by-module catalog with line
   counts and intra-crate dependencies.
3. [`03-public-api.md`](03-public-api.md) — entry points and grouped
   operations a consumer calls.
4. [`04-data-types-and-errors.md`](04-data-types-and-errors.md) — domain
   types, builder type-states, error taxonomy.
5. [`05-traits-and-extensibility.md`](05-traits-and-extensibility.md) —
   every public trait and its concrete implementations.
6. [`06-transport-and-serialization.md`](06-transport-and-serialization.md) —
   indexer REST client, endpoints, Borsh + serde split, SSE.
7. [`07-cryptography.md`](07-cryptography.md) — keys, Schnorr/ElGamal,
   signing flavors, key derivation.
8. [`08-stealth-and-privacy.md`](08-stealth-and-privacy.md) — stealth
   transfer subsystem.
9. [`09-end-to-end-flow.md`](09-end-to-end-flow.md) — one operation traced
   through every layer with file:line refs.
10. [`10-external-deps.md`](10-external-deps.md) — workspace dependencies
    and what each provides.
11. [`11-examples.md`](11-examples.md) — walkthrough of `examples/*.rs`.

## Conventions in these docs

- Each file is kept under 200 lines (the project rule, applies to docs too).
- Cross-references use relative links.
- Code snippets are illustrative Rust — real signatures, but trimmed.
- File:line references look like
  `crates/wallet/ootle-rs/src/provider/indexer.rs:138`.
- A single Mermaid block diagram lives in `01-architecture.md`. Other docs
  use ASCII when a diagram helps.

## Out of scope here

- Python design recommendations (intentionally deferred to a later planning
  round).
- Implementation details of upstream workspace crates such as
  `tari_ootle_transaction`, `tari_ootle_wallet_crypto`, or
  `tari_indexer_client` — these are documented as black boxes via the seam
  `ootle-rs` consumes.
- Code review of the Rust crate. We document its shape, not its quality.
