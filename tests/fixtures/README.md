# Test fixtures

| File                       | Purpose                                           |
|----------------------------|---------------------------------------------------|
| `crypto_vectors.json`      | Per-method known-input/known-output WASM vectors. |
| `addresses_corpus.json`    | bech32m address strings + decoded byte fields.    |

## Hex encoding

All byte blobs are lowercase hex with **no `0x` prefix**. Empty buffers
are encoded as the empty string `""`. JSON `null` represents an absent
optional field (e.g. `memo`).

## Provenance

Each fixture file records the upstream `ootle-wasm` version and the
SHA-256 of the `.wasm` blob it was generated against. When a future
blob bump produces different outputs, the fixtures fail loudly and must
be regenerated.

## Regenerating

```
uv run python scripts/regen_fixtures.py
```

The script reuses the deterministic seed labels in
`scripts/regen_fixtures.py` so the corpus stays stable across runs as
long as the WASM blob behaves the same.
