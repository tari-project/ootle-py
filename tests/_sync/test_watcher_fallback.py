"""``PendingTransaction`` SSE-failure resilience (sync).

Hand-maintained sync mirror of ``tests/_async/test_watcher_fallback.py``
(this package is excluded from ``unasync``; see ``scripts/unasync.py``).

The async ``test_caller_cancellation_propagates`` has no sync counterpart: a
blocking ``Future.result()`` only raises ``CancelledError`` when the future
itself is cancelled by the watcher, so there is no caller-task cancellation to
distinguish.
"""

from __future__ import annotations

from concurrent.futures import Future

import pytest
from pytest_httpx import HTTPXMock

import ootle._sync._watcher._pending as pending_mod
from ootle._sync._transport import IndexerTransport
from ootle._sync._watcher import PendingTransaction
from ootle._types.transaction import TransactionId
from ootle.errors import TransactionRejectedError

_TX = TransactionId("deadbeef" * 8)
_FINALIZED_COMMIT = {"result": {"Finalized": {"final_decision": "Commit"}}}
_FINALIZED_ABORT = {
    "result": {
        "Finalized": {
            "final_decision": {"Abort": "ExecutionFailure"},
            "execution_result": {
                "finalize": {
                    "result": {
                        "Reject": {"ExecutionFailure": {"code": "TemplateError", "message": "boom"}}
                    }
                }
            },
        }
    }
}


class _StubWatcher:
    """Watcher whose registration future never finalises.

    With ``cancel=True`` the future is cancelled on registration, as on actor
    shutdown; otherwise it stays pending, as when no SSE event arrives.
    """

    def __init__(self, *, cancel: bool = True) -> None:
        self._cancel = cancel
        self.unregistered: list[str] = []

    def register(self, _tx_id: TransactionId) -> Future[str | None]:
        future: Future[str | None] = Future()
        if self._cancel:
            future.cancel()
        return future

    def unregister(self, tx_id: TransactionId) -> None:
        self.unregistered.append(tx_id)


def _pending(watcher: _StubWatcher, transport: IndexerTransport) -> PendingTransaction:
    return PendingTransaction(
        tx_id=_TX,
        _transport=transport,
        _watcher=watcher,  # pyright: ignore[reportArgumentType]  # stub mirrors the surface used
        _timeout=5.0,
    )


def _result_url(transport: IndexerTransport) -> str:
    return f"{transport.url}/transactions/{_TX}/result"


def test_watcher_cancel_falls_back_to_polling(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pending_mod, "_REST_POLL_INTERVAL", 0.001)
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json={"result": "Pending"})
    httpx_mock.add_response(url=_result_url(transport), json=_FINALIZED_COMMIT)
    watcher = _StubWatcher()
    outcome = _pending(watcher, transport).watch()
    transport.close()
    assert outcome.is_commit
    assert watcher.unregistered == [_TX]


def test_abort_surfaces_while_sse_is_silent(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An abort commits no receipt, so no SSE event comes; REST must report it."""
    monkeypatch.setattr(pending_mod, "_ABORT_POLL_INTERVAL", 0.001)
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json={"result": "Pending"})
    httpx_mock.add_response(url=_result_url(transport), json=_FINALIZED_ABORT)
    watcher = _StubWatcher(cancel=False)
    with pytest.raises(TransactionRejectedError, match="TemplateError"):
        _pending(watcher, transport).watch()
    transport.close()
    assert watcher.unregistered == [_TX]
