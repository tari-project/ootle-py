# Vendored `@tari-project/ootle-wasm` blob

This directory holds the WebAssembly bridge artefact that backs the entire
`ootle._crypto` layer:

```
ootle_wasm_bg.wasm    # binary blob; ~800 KB
VERSION               # upstream version + sha256 + fetch date + source URL
```

Both files are committed to git and shipped in the wheel as package data.
**Never edit them by hand.**

## Refreshing

```
make update-wasm WASM_VERSION=<x.y.z>
```

This invokes `scripts/update_wasm.py`, which downloads the npm tarball
`@tari-project/ootle-wasm@<x.y.z>`, extracts the blob, recomputes its
SHA-256, and rewrites `ootle_wasm_bg.wasm` and `VERSION` here.

The script does **not** auto-commit. Open a PR with the diff so reviewers
can confirm the version bump and the new hash.
