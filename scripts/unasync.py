#!/usr/bin/env python3
"""Regenerate ``src/ootle/_sync/`` and ``tests/_sync/`` from their async twins.

The ``_async/`` tree is the source of truth for I/O-touching code. The
``_sync/`` tree is generated from it by AST-token-rewriting via the
``unasync`` library plus the project-specific class-name substitutions
defined in ``ADDITIONAL_REPLACEMENTS`` below.

Usage::

    uv run python scripts/unasync.py                  # write into the repo
    uv run python scripts/unasync.py --out-dir DIR    # write into a scratch dir
    uv run python scripts/unasync.py --check          # exit non-zero on drift

``make unasync`` calls the first form. ``make ci-verify-sync`` calls the
second to compare the regenerated tree against the committed one.
"""

from __future__ import annotations

import argparse
import filecmp
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

# When this file is executed as a script, Python prepends ``scripts/`` to
# ``sys.path``, which would shadow the ``unasync`` library on disk with
# this file. Drop the conflicting entry before the import.
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

import unasync

if TYPE_CHECKING:
    from collections.abc import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

# Identifier substitutions on top of unasync's defaults (which already
# cover ``async``/``await`` keywords, ``AsyncIterator``/``AsyncIterable``/
# ``AsyncGenerator``, ``__aenter__``/``__aexit__``, ``__aiter__``/
# ``__anext__``, and the generic ``Async*`` class prefix → ``Sync*``).
ADDITIONAL_REPLACEMENTS: dict[str, str] = {
    # httpx / httpx-sse
    "AsyncClient": "Client",
    "aconnect_sse": "connect_sse",
    "aiter_sse": "iter_sse",
    "aiter_lines": "iter_lines",
    "aiter_bytes": "iter_bytes",
    "aiter_text": "iter_text",
    "aiter_raw": "iter_raw",
    "aclose": "close",
    # Cross-package import paths inside `from ootle._async.<X>` —
    # rewrite to `from ootle._sync.<X>`. Production code uses relative
    # imports (``from ._transport import ...``) so this only fires
    # inside tests.
    "_async": "_sync",
    # Project-specific class names. Each overrides the library's default
    # ``Async*`` → ``Sync*`` rewrite.
    "AsyncOotleClient": "OotleClient",
    "AsyncIndexerTransport": "IndexerTransport",
    "AsyncPendingTransaction": "PendingTransaction",
    "AsyncTransactionWatcher": "TransactionWatcher",
    "AsyncTransactionInputResolver": "TransactionInputResolver",
    "IAsyncAccount": "IAccount",
    "IAsyncFaucet": "IFaucet",
    "IAsyncComponent": "IComponent",
    # Stealth workstream — generated `_sync/stealth/` mirror.
    "AsyncStealthTransfer": "StealthTransfer",
    "AsyncWalletStealthAuthorizer": "WalletStealthAuthorizer",
    # `_crypto/_stealth_provider.py` ships both the async Protocol and a
    # sync mirror with the same shape. The generated `_sync/stealth/`
    # files reference the sync one.
    "StealthCryptoProvider": "SyncStealthCryptoProvider",
    # Test helpers in tests/_helpers/sse.py.
    "fake_aconnect_sse": "fake_connect_sse",
    # User-facing strings in `_async/client.py` whose async-vs-sync phrasing
    # would otherwise leak into the generated `_sync/` mirror. The leading
    # and trailing `""` come from how `unasync` strips a triple-quoted
    # string's outer quotes (it removes one quote on each side, leaving
    # the two inner quotes embedded in the lookup key).
    '""Async client for the Tari L2 indexer.""': ('""Client for the Tari L2 indexer.""'),
    "call `await open()` first.": "call `open()` first.",
}

# Async class-name references that survive inside docstrings, comments, and
# string literals. `unasync` rewrites identifier *tokens* but leaves the
# contents of string/comment tokens untouched, so docstrings in the generated
# tree keep their async class names. These are applied as whole-word text
# substitutions over the generated (non-hand-maintained) files, mirroring how
# the token rewriter renamed the corresponding code identifiers. Restricted to
# PascalCase identifiers so a substitution never clips a substring of a longer
# name.
DOCSTRING_REPLACEMENTS: dict[str, str] = {
    "AsyncClient": "Client",  # httpx
    "AsyncOotleClient": "OotleClient",
    "AsyncIndexerTransport": "IndexerTransport",
    "AsyncPendingTransaction": "PendingTransaction",
    "AsyncTransactionWatcher": "TransactionWatcher",
    "AsyncTransactionInputResolver": "TransactionInputResolver",
    "AsyncUnsignedTransactionBuilder": "SyncUnsignedTransactionBuilder",
    "AsyncWalletStealthAuthorizer": "WalletStealthAuthorizer",
    "AsyncStealthTransfer": "StealthTransfer",
    "IAsyncAccount": "IAccount",
    "IAsyncComponent": "IComponent",
    "IAsyncFaucet": "IFaucet",
}

# (relative-from, relative-to) tree pairs handled by the codegen pipeline.
PAIRS: tuple[tuple[str, str], ...] = (
    ("src/ootle/_async", "src/ootle/_sync"),
    ("tests/_async", "tests/_sync"),
)

# Paths under the `_async`/`_sync` trees whose async and sync forms diverge
# structurally (asyncio task + Future vs. a worker thread + threading
# primitives), so they are hand-maintained for *both* trees rather than
# generated.
#
# `_watcher` is permanently hand-maintained.
HANDMAINTAINED_DIRS: frozenset[str] = frozenset({"_watcher"})
# Directories under the `tests/_async` ↔ `tests/_sync` trees that are
# hand-maintained on the test side only. The stealth test corpus relies
# heavily on ``unittest.mock.AsyncMock`` and pytest-httpx async fixtures
# that the token rewriter cannot translate cleanly into a sync form;
# source-side stealth is generated normally.
HANDMAINTAINED_TEST_DIRS: frozenset[str] = frozenset({"stealth"})
HANDMAINTAINED_TEST_PREFIXES: tuple[str, ...] = ("test_watcher",)
# `_offload.py` diverges structurally (async awaits `asyncio.to_thread`;
# sync invokes the callable directly), so both trees are hand-maintained.
HANDMAINTAINED_FILES: frozenset[str] = frozenset({"_offload.py"})


def _is_handmaintained(path: Path) -> bool:
    if any(part in HANDMAINTAINED_DIRS for part in path.parts):
        return True
    if "tests" in path.parts and any(part in HANDMAINTAINED_TEST_DIRS for part in path.parts):
        return True
    if path.name in HANDMAINTAINED_FILES:
        return True
    return any(
        path.stem == prefix or path.stem.startswith(f"{prefix}_")
        for prefix in HANDMAINTAINED_TEST_PREFIXES
    )


def _make_rule(from_dir: Path, to_dir: Path) -> unasync.Rule:
    return unasync.Rule(
        fromdir=str(from_dir) + "/",
        todir=str(to_dir) + "/",
        additional_replacements=ADDITIONAL_REPLACEMENTS,
    )


def _iter_sources(in_root: Path, pairs: Sequence[tuple[str, str]]) -> list[Path]:
    """Sorted absolute paths of every generated ``*.py`` file under each ``_async`` tree.

    Hand-maintained files (see :func:`_is_handmaintained`) are skipped — they
    have separately-written ``_sync`` counterparts.
    """
    sources: list[Path] = []
    for src, _dst in pairs:
        root = in_root / src
        if root.is_dir():
            sources.extend(sorted(p for p in root.rglob("*.py") if not _is_handmaintained(p)))
    return sources


def regenerate(
    in_root: Path,
    out_root: Path,
    pairs: Sequence[tuple[str, str]] = PAIRS,
    *,
    skip_format: bool = False,
) -> list[Path]:
    """Regenerate every ``_sync`` tree under *out_root* from ``_async`` under *in_root*.

    Runs ``ruff format`` over the generated output (unless
    ``skip_format=True``) so the committed sync mirror matches the
    project's formatting rules. Returns the sorted list of files
    written.
    """
    rules = [_make_rule(in_root / s, out_root / d) for s, d in pairs]
    sources = _iter_sources(in_root, pairs)
    unasync.unasync_files([str(p) for p in sources], rules)

    written: list[Path] = []
    for _src, dst in pairs:
        out_dir = out_root / dst
        if out_dir.is_dir():
            written.extend(sorted(out_dir.rglob("*.py")))

    _apply_docstring_replacements(written)

    if not skip_format and written:
        targets = [str(out_root / dst) for _src, dst in pairs if (out_root / dst).is_dir()]
        if targets:
            subprocess.run(  # noqa: S603 — well-known argv, no shell
                ["uv", "run", "ruff", "format", *targets],  # noqa: S607 — `uv` on PATH by design
                check=True,
                cwd=str(REPO_ROOT),
                stdout=subprocess.DEVNULL,
            )
    return written


def _apply_docstring_replacements(written: list[Path]) -> None:
    """Rewrite async class names the token rewriter leaves inside strings/comments.

    Applies :data:`DOCSTRING_REPLACEMENTS` as whole-word text substitutions
    over each generated (non-hand-maintained) file. Hand-maintained sync
    files are skipped — they author their own sync docstrings.
    """
    if not DOCSTRING_REPLACEMENTS:
        return
    keys = sorted(DOCSTRING_REPLACEMENTS, key=len, reverse=True)
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keys) + r")\b")
    for path in written:
        if _is_handmaintained(path):
            continue
        text = path.read_text(encoding="utf-8")
        new = pattern.sub(lambda m: DOCSTRING_REPLACEMENTS[m.group(0)], text)
        if new != text:
            path.write_text(new, encoding="utf-8")


def _diff_trees(committed: Path, generated: Path) -> list[str]:
    """Recursive byte-level comparison; returns flat human-readable diffs.

    ``filecmp.dircmp`` defaults to ``shallow=True`` which can declare two
    files equal on a stat (size + mtime) match alone. We force a content
    comparison via ``filecmp.cmp(..., shallow=False)`` so the gate is
    immune to mtime/filesystem-timestamp coincidences.
    """
    if not committed.exists() and not generated.exists():
        return []
    if not committed.exists():
        return [f"unexpected tree (no committed counterpart): {generated}"]
    if not generated.exists():
        return [f"missing in generated output: {committed}"]
    cmp = filecmp.dircmp(committed, generated)
    diffs: list[str] = [
        *(
            f"only in committed: {committed / name}"
            for name in cmp.left_only
            if not _is_handmaintained(committed / name)
        ),
        *(
            f"only in generated: {generated / name}"
            for name in cmp.right_only
            if not _is_handmaintained(generated / name)
        ),
    ]
    for name in cmp.common_files:
        cf = committed / name
        gf = generated / name
        if not _is_handmaintained(cf) and not filecmp.cmp(str(cf), str(gf), shallow=False):
            diffs.append(f"differs: {cf}")
    for sub in cmp.common_dirs:
        if _is_handmaintained(committed / sub):
            continue
        diffs.extend(_diff_trees(committed / sub, generated / sub))
    return diffs


def _check() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        regenerate(REPO_ROOT, tmp_root)
        diffs: list[str] = []
        for _src, dst in PAIRS:
            diffs.extend(_diff_trees(REPO_ROOT / dst, tmp_root / dst))
    if diffs:
        print("unasync drift detected:", file=sys.stderr)
        for line in diffs:
            print(f"  {line}", file=sys.stderr)
        print(
            "Run `make unasync` and commit the resulting changes.",
            file=sys.stderr,
        )
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write generated trees beneath DIR (mirrors src/ and tests/) instead "
        "of the repo. Useful for inspection or external diffing; the CI drift "
        "gate uses --check.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Generate to a temp dir and exit non-zero on any diff vs. the "
        "committed `_sync/` trees. Mutually exclusive with --out-dir.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.check and args.out_dir is not None:
        parser.error("--check and --out-dir are mutually exclusive")
    if args.check:
        return _check()
    out_root = args.out_dir.resolve() if args.out_dir else REPO_ROOT
    regenerate(REPO_ROOT, out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
