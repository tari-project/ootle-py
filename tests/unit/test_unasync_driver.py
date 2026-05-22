"""Tests for the ``scripts/unasync.py`` codegen driver.

The driver lives outside the package and outside pyright's include set,
so we load it via ``importlib`` and exercise its public ``regenerate``
helper against a tiny, self-contained ``_async`` source tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

DRIVER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "unasync.py"

ASYNC_SAMPLE = """\
from collections.abc import AsyncIterator


class Service:
    async def fetch(self, transport: AsyncIndexerTransport) -> int:
        async with transport.session() as s:
            return await s.get("balance")

    async def stream(self) -> AsyncIterator[int]:
        async for item in self._items():
            yield item
"""

SYNC_EXPECTED = """\
from collections.abc import Iterator


class Service:
    def fetch(self, transport: IndexerTransport) -> int:
        with transport.session() as s:
            return s.get("balance")

    def stream(self) -> Iterator[int]:
        for item in self._items():
            yield item
"""


def _load_driver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ootle_unasync_driver", DRIVER_PATH)
    if spec is None or spec.loader is None:
        msg = f"could not load driver spec from {DRIVER_PATH}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver() -> ModuleType:
    return _load_driver()


def test_regenerate_rewrites_async_to_sync(driver: ModuleType, tmp_path: Path) -> None:
    src_async = tmp_path / "src" / "ootle" / "_async"
    src_async.mkdir(parents=True)
    (src_async / "service.py").write_text(ASYNC_SAMPLE, encoding="utf-8")

    written = cast(
        "list[Path]",
        driver.regenerate(  # pyright: ignore[reportAny]
            in_root=tmp_path,
            out_root=tmp_path,
            pairs=(("src/ootle/_async", "src/ootle/_sync"),),
        ),
    )

    out_path = tmp_path / "src" / "ootle" / "_sync" / "service.py"
    assert written == [out_path]
    assert out_path.read_text(encoding="utf-8") == SYNC_EXPECTED


def test_additional_replacements_match_architecture_spec(driver: ModuleType) -> None:
    """Locks the substitution table against accidental drift.

    Equality (not subset) so that adding or removing entries to the
    driver without updating this list — and vice versa — fails the
    test, keeping the expected table and the code in lockstep.
    """
    replacements = cast("dict[str, str]", driver.ADDITIONAL_REPLACEMENTS)  # pyright: ignore[reportAny]
    expected: dict[str, str] = {
        "AsyncClient": "Client",
        "aconnect_sse": "connect_sse",
        "aiter_sse": "iter_sse",
        "aiter_lines": "iter_lines",
        "aiter_bytes": "iter_bytes",
        "aiter_text": "iter_text",
        "aiter_raw": "iter_raw",
        "aclose": "close",
        "_async": "_sync",
        "AsyncOotleClient": "OotleClient",
        "AsyncIndexerTransport": "IndexerTransport",
        "AsyncPendingTransaction": "PendingTransaction",
        "AsyncTransactionWatcher": "TransactionWatcher",
        "AsyncTransactionInputResolver": "TransactionInputResolver",
        "IAsyncAccount": "IAccount",
        "IAsyncFaucet": "IFaucet",
        "IAsyncComponent": "IComponent",
        "AsyncStealthTransfer": "StealthTransfer",
        "AsyncWalletStealthAuthorizer": "WalletStealthAuthorizer",
        "StealthCryptoProvider": "SyncStealthCryptoProvider",
        "fake_aconnect_sse": "fake_connect_sse",
        '""Async client for the Tari L2 indexer.""': ('""Client for the Tari L2 indexer.""'),
        "call `await open()` first.": "call `open()` first.",
    }
    assert replacements == expected


def test_check_mode_passes_against_committed_tree(driver: ModuleType) -> None:
    rc: Any = driver._check()  # pyright: ignore[reportPrivateUsage, reportAny]
    assert rc == 0
