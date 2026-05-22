# CLAUDE.md — Engineering Guide for `ootle`

The authoritative engineering contract for any contributor — human or AI — in
this repository. Read it before you write code. Follow it strictly.

---

## 0. What this project is

`ootle-py` (PyPI distribution name; importable as `ootle`) is the **Python client
library for the Tari L2 network** (codename *Ootle*). It is the Pythonic
counterpart to the upstream Rust crate `ootle-rs` and the official JavaScript
package `@tari-project/ootle-wasm`.

The goal is to give Python developers an idiomatic, async-first library for
interacting with Ootle indexers — querying chain state, sending transactions,
watching for finalisation, and composing template invocations — with parity to
the wire protocol the Rust client speaks.

### Reference points

- **Rust upstream:** `crates/wallet/ootle-rs/` in the Tari workspace.
  Architectural reference at [`docs/ootle-rs/`](docs/ootle-rs/) — 11 documents
  describing the crate's layers, traits, types, transport, and crypto.
- **Local Rust checkout (`$OOTLE_RS_PATH`).** Agents and scripts that
  need to read the Rust source (parity checks, fixture regeneration,
  "what does the upstream actually do?") resolve the path through this
  environment variable. The repo ships a committed `.envrc` that runs
  `dotenv_if_exists`, so:
  ```bash
  cp .env.example .env       # then edit OOTLE_RS_PATH for your machine
  direnv allow               # one-time authorisation
  ```
  `.env` is gitignored — no personal absolute paths land in git. If
  `$OOTLE_RS_PATH` is unset, agents should ask the user for the path
  rather than guess.
- **JavaScript counterpart:** [`@tari-project/ootle-wasm`](https://www.npmjs.com/package/@tari-project/ootle-wasm)
  — the WASM blob from this package is **vendored** into our crypto layer.

### Core architectural decisions (locked)

These are the locked decisions from the project's planning round.
Honour them; revisit only with explicit user agreement.

| Topic               | Decision |
|---------------------|----------|
| Cryptography        | The `@tari-project/ootle-wasm` blob is vendored at `src/ootle/_crypto/wasm/` and loaded via `wasmtime-py`. All Ristretto/Schnorr/Borsh work goes through this bridge. No Python-side reimplementation. |
| Concurrency model   | **Async-first**: `src/ootle/_async/` is the source of truth. `src/ootle/_sync/` is **generated** by `unasync` at build time and committed to the repo. CI verifies the two trees stay in sync. |
| Public surface      | `from ootle import OotleClient, AsyncOotleClient, OotleWallet, …` — both clients ship in v1, identical in shape, sync vs. async. |
| v1 scope            | Read-only queries + public transfers + multi-signer co-signing. The faucet (public path), `IAccount`, `IComponent`, dry-run, and event watching all ship in v1. Stealth transfers (revealed + stealth outputs, multi-input aggregation, faucet stealth path, UTXO read helpers) also ship, backed by the same WASM blob. |
| Stealth / privacy   | **Shipped on the vendored `ootle-wasm` blob.** Upstream now exports the stealth primitives (bulletproofs, ElGamal viewable-balance, balance-proof signatures, `aggregateInputMasks`), so `WasmCryptoProvider` natively satisfies both `CryptoProvider` and `StealthCryptoProvider`. The interim wallet-daemon JSON-RPC backend was built, proven, then removed. |
| Wire compatibility  | Same indexer REST + SSE endpoints as `ootle-rs`. Byte-identical `TransactionEnvelope` (the WASM lib produces it). |
| Borsh in Python     | **Not implemented.** All Borsh encoding/decoding is delegated to WASM. |
| HD / BIP-32 / mnemonics | Out of scope, both in v1 and v2. Caller-application concern. |
| Distribution        | Pure-Python wheel (`py3-none-any`). The `.wasm` blob ships as package data. No platform-specific wheels. |
| Domain types        | `@dataclass(frozen=True, slots=True)` everywhere; hand-rolled JSON helpers for the few wire shapes. No pydantic. |
| HTTP transport      | `httpx` (sync + async) plus `httpx-sse` for the SSE channels. |

### Layered architecture

Six layers, mirroring `ootle-rs` conceptually but using Python-idiomatic file
splits. Layers 4 (domain types) and 6 (crypto bridge) are pure-sync and shared
between both clients; layers 1, 2, and 5 have an `_async/` source-of-truth and
a `_sync/` generated mirror.

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer 1 · User-facing API   OotleClient / AsyncOotleClient       │
│ Layer 2 · Templates / DSL   IAccount, IFaucet, IComponent        │
│ Layer 3 · Wallet & signing  OotleWallet, LocalSigner             │
│ Layer 4 · Domain types      Address, OotleSecretKey, Substate, … │
│ Layer 5 · Transport & wire  httpx + httpx-sse, resolver, watcher │
│ Layer 6 · Crypto bridge     wasmtime-py + ootle_wasm_bg.wasm     │
└──────────────────────────────────────────────────────────────────┘
```

### What we are working towards (high level)

The work is sequenced through these milestones:

0. **Foundations & WASM bridge** — vendor the blob, port the `wasm-bindgen`
   glue, expose a `CryptoProvider` Protocol.
1. **Domain types + wallet + signing** — pure-Python, no I/O.
2. **Read-only async client** — `AsyncOotleClient` with balance / substate
   queries against a LocalNet indexer.
3. **`unasync` infrastructure** — sync mirror generated and committed.
4. **Transaction send + watch** — faucet path, per-pending-tx SSE.
5. **Account transfers + multi-signer** — `IAccount` builder, co-authorisation.
6. **Component DSL + dry-run + event watching** — full `IComponent`,
   fee estimation, template events.
7. **Polish, docs, first PyPI release (`0.1.0`).**
8. **Stealth & privacy** — **shipped on the vendored WASM blob.** Upstream
   exposed the stealth primitives; an interim wallet-daemon JSON-RPC backend
   was built then removed once the WASM path was proven.

When in doubt about scope, file layout, or the public API shape, ask before
diverging. The locked decisions above are the contract.

---

## 1. Stack

| Aspect          | Choice                                 |
| --------------- | -------------------------------------- |
| Language        | Python **>= 3.13** (CPython)           |
| Package & env   | **uv** (sole orchestrator)             |
| Lint & format   | **Ruff**                               |
| Static typing   | **Pyright** (strict)                   |
| Tests           | **pytest** + **pytest-cov**            |
| Task runners    | **Make** (primary) and **just**        |
| Layout          | `src/` layout — package in `src/ootle` |

Versions are pinned in `pyproject.toml`. Do not add a second package manager,
formatter, linter, or type checker.

---

## 2. Golden Rules (non-negotiable)

1. **Type hints are mandatory.** Every function, method, parameter, and return
   value carries an explicit, accurate annotation. Use modern PEP 604 syntax
   (`int | None`, never `Optional[int]`) and PEP 585 generics (`list[int]`).
   Pyright strict mode must pass with zero errors.
2. **Code files stay under 200 lines.** No source or configuration file may
   exceed **200 lines**. Documentation files (`.md`) may exceed this when
   the content warrants it. When a code file approaches the limit, refactor
   it: extract logic into modules or submodules, split a class, or move
   helpers into siblings. Small files are a feature, not a constraint.
3. **`make ci` is the source of truth.** If it fails locally, it fails in CI.
4. **No silent regressions.** Update or add tests when behaviour changes;
   coverage stays at or above the configured floor.
5. **Conventions over creativity.** Follow existing patterns first.

---

## 3. The 200-Line Limit (How to Apply)

- Counts every physical line: code, comments, blank lines. Use `wc -l`.
- Applies to source files, tests, and configuration files. Documentation
  files (`.md`) are exempt. Generated files (lockfiles) are also exempt.
- When a module is approaching the limit, **stop and refactor** rather than
  tipping over. Strategies, in order:
  1. Extract pure functions into a sibling module (`utils.py`, `types.py`).
  2. Convert the module into a package: turn `foo.py` into `foo/__init__.py`
     plus `foo/<topic>.py` submodules; re-export the public surface.
  3. Split a class into composed smaller classes when the class is the bloat.
- Tests are not exempt — a 400-line test file means the unit under test does
  too much.

---

## 4. Daily Workflow

The everyday loop runs through `make`. The `justfile` mirrors it; the two
stay in sync.

| Command            | What it does                                              |
| ------------------ | --------------------------------------------------------- |
| `make help`        | List all targets with descriptions.                       |
| `make sync`        | `uv sync --all-groups` — install runtime + dev deps.      |
| `make upgrade`     | Refresh the lockfile and re-sync.                         |
| `make lint`        | Run Ruff lint checks.                                     |
| `make lint-fix`    | Auto-fix Ruff findings.                                   |
| `make format`      | Apply Ruff's formatter.                                   |
| `make format-check`| Verify formatting without writing.                        |
| `make typecheck`   | Run Pyright in strict mode.                               |
| `make test`        | Run pytest. Pass extras via `ARGS="-k pattern"`.          |
| `make coverage`    | Run pytest with coverage reporting.                       |
| `make check`       | format → lint-fix → typecheck → test (local pass).        |
| `make ci`          | Strict CI gate.                                           |
| `make run`         | Run the `ootle` CLI. `ARGS="..."` forwards arguments.     |
| `make build`       | Wheel + sdist into `dist/`.                               |
| `make clean`       | Remove caches, build output, coverage artefacts.          |

The same recipes are exposed via `just <recipe>` (e.g. `just ci`,
`just test -- -k cli`). Use whichever fits your environment — every change
must satisfy `make ci` before it lands.

### Examples

```bash
make test ARGS="-k test_main_accepts_name_argument"
make run ARGS="--version"
uv add httpx                  # runtime dependency
uv add --group dev mypy       # dev-only dependency
```

Never edit the dependency lists in `pyproject.toml` by hand — let `uv` keep
the lockfile in sync.

---

## 5. Code Style

Ruff governs style; the configuration in `pyproject.toml` is the single source
of truth. Avoid inline `# noqa` unless you can justify it in review.

- **Line length:** 100. **Quotes:** double. **Imports:** sorted by Ruff's isort.
- **Naming:** PEP 8 — snake_case, PascalCase, UPPER_SNAKE.
- **Comments:** add only when the *why* is non-obvious. Never describe *what*.
- **Docstrings:** required on public modules, classes, and functions; Google
  style; tight.
- **`Any` is a smell.** Reach for it only when no narrower type exists; prefer
  `typing.cast` over `# type: ignore` when bridging untyped APIs.
- **`pathlib` over `os.path`.** Always.
- **Logging over `print`** for anything beyond CLI output.

---

## 6. Typing Discipline

- Pyright runs in **strict** mode. Every public surface needs precise types.
- Use `from __future__ import annotations` for lightweight imports.
- Prefer `collections.abc` (`Sequence`, `Mapping`, `Iterable`) for parameters
  and concrete types (`list`, `dict`) for returns when ownership matters.
- Reach for `TypedDict`, `Protocol`, `dataclass`, or `NamedTuple` over loose
  dicts and tuples.
- New code must not trigger any `reportUnknown*` diagnostics. Tests are typed.

---

## 7. Testing Discipline

- Tests live in `tests/`, mirroring the package layout.
- Name files `test_*.py` and functions `test_*`.
- Use `pytest` features (`fixtures`, `parametrize`, `monkeypatch`) over manual
  setup/teardown.
- Custom markers must be registered in `pyproject.toml` (`--strict-markers`).
- Default warning filter is `error` — surface deprecations early.
- Coverage floor is enforced (`fail_under = 80`). Raise it; never lower it
  without team agreement.

---

## 8. Project Layout

```
ootle-python/
├── CLAUDE.md                           # this file
├── Makefile                            # primary task runner
├── justfile                            # alternate task runner (kept in sync)
├── pyproject.toml                      # tool configuration & dependencies
├── README.md
├── docs/
│   └── ootle-rs/                       # architectural reference for the Rust upstream
├── scripts/
│   ├── unasync.py                      # generate src/ootle/_sync/ from src/ootle/_async/
│   └── update_wasm.py                  # refresh the vendored ootle-wasm blob
├── src/ootle/                          # the package — modules under 200 lines
│   ├── __init__.py                     # public exports
│   ├── __main__.py / cli.py
│   ├── _version.py
│   ├── errors.py                       # exception taxonomy (sync, shared)
│   ├── wallet.py                       # OotleWallet (sync, shared)
│   ├── _signing.py                     # LocalSigner, Signer Protocol (sync, shared)
│   ├── _instructions.py                # args(), workspace() (sync, shared)
│   ├── _types/                         # frozen dataclasses (sync, shared)
│   ├── _crypto/                        # WASM bridge (sync, shared)
│   │   └── wasm/                       # vendored .wasm blob + VERSION
│   ├── _async/                         # SOURCE OF TRUTH for async I/O
│   │   ├── client.py
│   │   ├── _transport.py
│   │   ├── _resolver.py
│   │   ├── _watcher.py
│   │   ├── _events.py
│   │   └── builders/
│   └── _sync/                          # GENERATED mirror — committed, drift-checked
│       └── …
└── tests/                              # mirrors src/ootle/
    ├── unit/                           # pure-logic, no I/O, no WASM
    ├── _async/                         # source-of-truth async tests
    ├── _sync/                          # generated sync mirror
    └── integration/                    # marker-gated, LocalNet indexer required
```

### Public / internal boundary

- The leading-underscore packages (`_async`, `_sync`, `_crypto`, `_types`,
  `_signing`, `_instructions`) are **internal**. Users import from the
  top-level `ootle` only.
- A name not in `src/ootle/__init__.py.__all__` may be renamed/moved without
  a major-version bump.
- New features default to a new submodule (`src/ootle/<feature>.py`) or, when
  they have multiple cohesive pieces, a subpackage. Async-touching features
  go in `_async/` and the corresponding `_sync/` file is regenerated.

### `_async/` ↔ `_sync/` discipline

- **Always edit `_async/`.** Never hand-edit `_sync/`.
- After any change in `_async/`: run `make unasync`, commit the resulting
  `_sync/` changes in the same commit, run `make ci`.
- `make ci-verify-sync` regenerates `_sync/` to a temp dir and asserts
  byte-equality with the committed mirror — drift fails the build.
- Substitution rules (e.g. `httpx.AsyncClient → httpx.Client`,
  `aconnect_sse → connect_sse`, class-name maps) live in
  `scripts/unasync.py`.

### The vendored WASM blob

- The `.wasm` artefact lives at `src/ootle/_crypto/wasm/ootle_wasm_bg.wasm`,
  committed to git as binary package data.
- `src/ootle/_crypto/wasm/VERSION` records the upstream `ootle-wasm` version,
  the SHA-256 of the blob, and the fetch date. The bridge **verifies the
  hash at load** and refuses to instantiate on mismatch.
- Refresh procedure: `make update-wasm WASM_VERSION=<x.y.z>`. This is a
  deliberate human-in-the-loop PR — bumps are reviewed, not automated.
- Never edit the blob or `VERSION` by hand. Never `.gitignore` either.

---

## 9. Commits & PRs

- Small, focused commits. One logical change each.
- Imperative messages (`Add`, `Fix`, `Refactor`); the body explains *why*.
- Run `make ci` locally before opening a PR.
- PRs document: what changed, why, how it was tested, follow-ups.

---

## 10. Anti-Patterns (Don't)

- Add a second formatter / linter / type checker.
- Skip type hints "because it's just a script".
- Disable Pyright strict mode to silence diagnostics — narrow the type instead.
- Add `# noqa` / `# type: ignore` without an inline reason.
- Let a code or config file cross 200 lines — refactor.
- Introduce ad-hoc shell scripts when a `make` / `just` recipe will do.
- Commit caches, coverage data, or build artefacts.
- Add features, abstractions, or "future-proofing" beyond the task.

---

## 11. Quick Reference

```bash
make sync                          # bootstrap the environment
make check                         # local pre-commit pass
make ci                            # exact CI gate (includes unasync + WASM gates)
make test ARGS="-k name"           # run a single test
make run ARGS="--version"          # run the CLI
make unasync                       # regenerate src/ootle/_sync/ from _async/
make update-wasm WASM_VERSION=x.y  # refresh the vendored ootle-wasm blob
```

### Reference

- [`docs/ootle-rs/`](docs/ootle-rs/) — architectural reference for the Rust
  upstream that this client mirrors.

Fix gaps in this document in the same PR as the change that exposed them.
