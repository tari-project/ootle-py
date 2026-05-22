"""``AsyncPendingTransaction`` SSE-failure resilience.

When the SSE wait yields nothing — the watcher stopped before finalisation —
``watch()`` must fall back to polling REST for the remaining budget rather than
issuing a single query, and it must still propagate a genuine cancellation of
the caller's own task. (Hand-maintained — separate ``tests/_sync`` mirror;
see ``scripts/unasync.py``.)
"""

from __future__ import annotations

import asyncio

import pytest
from pytest_httpx import HTTPXMock

import ootle._async._watcher._pending as pending_mod
from ootle._async._transport import AsyncIndexerTransport
from ootle._async._watcher import AsyncPendingTransaction
from ootle._types.transaction import TransactionId

_TX = TransactionId("deadbeef" * 8)
_FINALIZED_COMMIT = {"result": {"Finalized": {"final_decision": "Commit"}}}


class _StubWatcher:
    """Watcher whose registration future never finalises.

    With ``cancel=True`` the future is cancelled on registration, mirroring the
    actor settling outstanding futures on shutdown; otherwise it stays pending
    so the caller can cancel ``watch()`` itself.
    """

    def __init__(self, *, cancel: bool) -> None:
        self._cancel = cancel
        self.unregistered: list[str] = []

    def register(self, _tx_id: TransactionId) -> asyncio.Future[str | None]:
        future: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        if self._cancel:
            future.cancel()
        return future

    def unregister(self, tx_id: TransactionId) -> None:
        self.unregistered.append(tx_id)


def _pending(watcher: _StubWatcher, transport: AsyncIndexerTransport) -> AsyncPendingTransaction:
    return AsyncPendingTransaction(
        tx_id=_TX,
        _transport=transport,
        _watcher=watcher,  # pyright: ignore[reportArgumentType]  # stub mirrors the surface used
        _timeout=5.0,
    )


def _result_url(transport: AsyncIndexerTransport) -> str:
    return f"{transport.url}/transactions/{_TX}/result"


async def test_watcher_cancel_falls_back_to_polling(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pending_mod, "_REST_POLL_INTERVAL", 0.001)
    transport = AsyncIndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json={"result": "Pending"})
    httpx_mock.add_response(url=_result_url(transport), json=_FINALIZED_COMMIT)
    watcher = _StubWatcher(cancel=True)
    outcome = await _pending(watcher, transport).watch()
    await transport.aclose()
    assert outcome.is_commit
    assert watcher.unregistered == [_TX]


async def test_caller_cancellation_propagates() -> None:
    transport = AsyncIndexerTransport("http://idx")
    task = asyncio.ensure_future(_pending(_StubWatcher(cancel=False), transport).watch())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await transport.aclose()
