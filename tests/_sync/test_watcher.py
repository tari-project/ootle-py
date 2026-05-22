"""``PendingTransaction`` tests — SSE result, REST fallback, receipt, timeout.

Hand-maintained sync mirror of ``tests/_async/test_watcher.py`` (this
package is excluded from ``unasync``; see ``scripts/unasync.py``).
"""

from __future__ import annotations

import json
from concurrent.futures import Future

import pytest
from pytest_httpx import HTTPXMock

import ootle._sync._watcher._pending as pending_mod
from ootle._sync._transport import IndexerTransport
from ootle._sync._watcher import PendingTransaction
from ootle._types._sse_events import parse_finalized_event
from ootle._types.reject_reason import ExecutionFailure
from ootle._types.transaction import TransactionId
from ootle.errors import IndexerClientError, TransactionRejectedError, TransactionTimeoutError

_TX = TransactionId("deadbeef" * 8)

_FINALIZED_COMMIT = {"result": {"Finalized": {"final_decision": "Commit"}}}
_FINALIZED_REJECT = {
    "result": {
        "Finalized": {
            "final_decision": {"Abort": "exec failed"},
            "execution_result": {
                "finalize": {"result": {"Reject": {"ExecutionFailure": "exec failed"}}}
            },
            "abort_details": "exec failed",
        }
    }
}
_RECEIPT_BODY = {
    "receipt": {
        "epoch": 7,
        "fee_receipt": {
            "total_fee_payment": 100,
            "total_fees_paid": 100,
            "total_fee_overcharge": 0,
        },
    }
}


class _StubWatcher:
    """Stand-in for :class:`TransactionWatcher` with a canned outcome."""

    def __init__(self, *, tag: str | None = None, finalize: bool = True) -> None:
        self._tag = tag
        self._finalize = finalize
        self.unregistered: list[str] = []

    def register(self, _tx_id: TransactionId) -> Future[str | None]:
        future: Future[str | None] = Future()
        if self._finalize:
            future.set_result(self._tag)
        return future

    def unregister(self, tx_id: TransactionId) -> None:
        self.unregistered.append(tx_id)


def _pending(
    transport: IndexerTransport, watcher: _StubWatcher | None, *, timeout: float = 0.05
) -> PendingTransaction:
    return PendingTransaction(
        tx_id=_TX,
        _transport=transport,
        _watcher=watcher,  # pyright: ignore[reportArgumentType]  # _StubWatcher mirrors the surface used
        _timeout=timeout,
    )


def _result_url(transport: IndexerTransport) -> str:
    return f"{transport.url}/transactions/{_TX}/result"


def test_watch_commit_via_sse() -> None:
    transport = IndexerTransport("http://idx")
    watcher = _StubWatcher(tag="Commit")
    outcome = _pending(transport, watcher).watch()
    transport.close()
    assert outcome.is_commit
    assert watcher.unregistered == [_TX]


def test_watch_fee_intent_resolves_via_rest_reject(httpx_mock: HTTPXMock) -> None:
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json=_FINALIZED_REJECT)
    with pytest.raises(TransactionRejectedError) as exc:
        _pending(transport, _StubWatcher(tag="FeeIntentCommit")).watch()
    transport.close()
    assert exc.value.tx_id == _TX
    assert exc.value.reject_reason == ExecutionFailure(message="exec failed")


def test_watch_timeout_then_rest_pending(httpx_mock: HTTPXMock) -> None:
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json={"result": "Pending"})
    with pytest.raises(TransactionTimeoutError):
        _pending(transport, _StubWatcher(finalize=False)).watch()
    transport.close()


def test_watch_timeout_then_rest_finalized_commit(httpx_mock: HTTPXMock) -> None:
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json=_FINALIZED_COMMIT)
    outcome = _pending(transport, _StubWatcher(finalize=False)).watch()
    transport.close()
    assert outcome.is_commit


def test_watch_no_watcher_polls_rest(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pending_mod, "_REST_POLL_INTERVAL", 0.001)
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json={"result": "Pending"})
    httpx_mock.add_response(url=_result_url(transport), json=_FINALIZED_COMMIT)
    outcome = _pending(transport, None, timeout=5.0).watch()
    transport.close()
    assert outcome.is_commit


def test_watch_no_watcher_times_out(httpx_mock: HTTPXMock) -> None:
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=_result_url(transport), json={"result": "Pending"})
    with pytest.raises(TransactionTimeoutError):
        _pending(transport, None, timeout=0.0).watch()
    transport.close()


def test_with_timeout_returns_new_handle() -> None:
    transport = IndexerTransport("http://idx")
    pending = _pending(transport, _StubWatcher(tag="Commit"), timeout=10.0)
    rebound = pending.with_timeout(99.0)
    transport.close()
    assert rebound is not pending
    assert rebound._timeout == 99.0  # pyright: ignore[reportPrivateUsage]  # internal access
    assert rebound.tx_id == pending.tx_id


def test_get_receipt_round_trips(httpx_mock: HTTPXMock) -> None:
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=f"http://idx/transaction-receipts/{_TX}", json=_RECEIPT_BODY)
    receipt = _pending(transport, None).get_receipt()
    transport.close()
    assert receipt.epoch == 7


def test_get_receipt_retries_then_succeeds(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pending_mod, "_RECEIPT_POLL_INTERVAL", 0.0)
    transport = IndexerTransport("http://idx")
    url = f"http://idx/transaction-receipts/{_TX}"
    httpx_mock.add_response(url=url, status_code=404)
    httpx_mock.add_response(url=url, json=_RECEIPT_BODY)
    receipt = _pending(transport, None).get_receipt()
    transport.close()
    assert receipt.epoch == 7


def test_get_receipt_404_raises(httpx_mock: HTTPXMock) -> None:
    transport = IndexerTransport("http://idx")
    httpx_mock.add_response(url=f"http://idx/transaction-receipts/{_TX}", status_code=404)
    with pytest.raises(IndexerClientError):
        _pending(transport, None).get_receipt(timeout=0.0)
    transport.close()


def test_parse_finalized_event_variants() -> None:
    assert parse_finalized_event("not json") is None
    assert parse_finalized_event("[1, 2]") is None
    assert parse_finalized_event(json.dumps({"outcome": "Commit"})) is None
    assert parse_finalized_event(json.dumps({"transaction_id": "tx", "outcome": "Commit"})) == (
        "tx",
        "Commit",
    )
    nested = json.dumps({"transaction_id": "tx", "outcome": {"Commit": None}})
    assert parse_finalized_event(nested) == ("tx", "Commit")
    assert parse_finalized_event(json.dumps({"transaction_id": "tx", "outcome": 42})) == (
        "tx",
        None,
    )
