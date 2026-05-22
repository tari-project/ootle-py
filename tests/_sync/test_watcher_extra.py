"""``TransactionWatcher`` actor internals + transport wiring (sync).

Hand-maintained sync mirror of ``tests/_async/test_watcher_extra.py``.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

import httpx
import pytest

import ootle._sync._watcher._actor as actor_mod
from ootle._sync._transport import IndexerTransport
from ootle._sync._watcher import TransactionWatcher
from ootle._types.transaction import TransactionId
from tests._helpers.sse import fake_connect_sse

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx_sse import ServerSentEvent

_TX = TransactionId("deadbeef" * 8)


class _Sse:
    __slots__ = ("data", "event")

    def __init__(self, event: str, data: str) -> None:
        self.event = event
        self.data = data


def _sse(event: str, data: str) -> ServerSentEvent:
    return cast("ServerSentEvent", _Sse(event, data))


def _commit_event(tx_id: str = _TX) -> tuple[str, str]:
    return ("TransactionFinalized", json.dumps({"transaction_id": tx_id, "outcome": "Commit"}))


class _Failing:
    """A context manager whose entry mimics an unreachable ``/events`` endpoint."""

    def __enter__(self) -> object:
        raise httpx.ConnectError("refused")

    def __exit__(self, *_a: object) -> None:
        return None


def _serving(*events: tuple[str, str], keep_open: bool = True) -> Callable[..., object]:
    """A ``_open_sse_stream`` stand-in that always serves a fresh source of *events*."""

    def _open(*_a: object, **_k: object) -> object:
        return fake_connect_sse(list(events), keep_open=keep_open)

    return _open


def _serving_sequence(*sources: object) -> Callable[..., object]:
    """A ``_open_sse_stream`` stand-in that hands out each of *sources* in turn."""
    it = iter(sources)

    def _open(*_a: object, **_k: object) -> object:
        return next(it)

    return _open


def _failing_stream() -> Callable[..., object]:
    def _open(*_a: object, **_k: object) -> object:
        return _Failing()

    return _open


def _watcher() -> tuple[IndexerTransport, TransactionWatcher]:
    transport = IndexerTransport("http://idx")
    return transport, TransactionWatcher(transport.client, transport.url)


def test_dispatch_resolves_registered_future() -> None:
    transport, watcher = _watcher()
    future = watcher.register(_TX)
    watcher._dispatch(_sse(*_commit_event()))  # pyright: ignore[reportPrivateUsage]  # internal access
    transport.close()
    assert future.result() == "Commit"


def test_dispatch_ignores_noise() -> None:
    transport, watcher = _watcher()
    future = watcher.register(_TX)
    watcher._dispatch(_sse("OtherEvent", "{}"))  # pyright: ignore[reportPrivateUsage]  # internal access
    watcher._dispatch(_sse("TransactionFinalized", "not json"))  # pyright: ignore[reportPrivateUsage]  # internal access
    watcher._dispatch(_sse(*_commit_event("other_tx")))  # pyright: ignore[reportPrivateUsage]  # internal access
    transport.close()
    assert not future.done()


def test_register_is_idempotent_then_fresh_after_dispatch() -> None:
    transport, watcher = _watcher()
    first = watcher.register(_TX)
    assert watcher.register(_TX) is first
    watcher._dispatch(_sse(*_commit_event()))  # pyright: ignore[reportPrivateUsage]  # internal access
    assert watcher.register(_TX) is not first
    watcher.unregister(_TX)
    transport.close()


def test_start_dispatches_via_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving(_commit_event()))
    future = watcher.register(_TX)
    watcher.start()
    tag = future.result(1.0)
    watcher.close()
    transport.close()
    assert tag == "Commit"


def test_start_propagates_connect_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _failing_stream())
    with pytest.raises(httpx.ConnectError):
        watcher.start()
    transport.close()


def test_reconnects_after_stream_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = _watcher()
    monkeypatch.setattr(actor_mod, "_RECONNECT_DELAY", 0.001)
    monkeypatch.setattr(
        actor_mod,
        "_open_sse_stream",
        _serving_sequence(
            fake_connect_sse([], keep_open=False),
            fake_connect_sse([_commit_event()], keep_open=True),
        ),
    )
    future = watcher.register(_TX)
    watcher.start()
    tag = future.result(1.0)
    watcher.close()
    transport.close()
    assert tag == "Commit"


def test_aclose_settles_outstanding(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving())
    future = watcher.register(_TX)
    watcher.start()
    watcher.close()
    transport.close()
    assert future.cancelled()


def test_start_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving())
    watcher.start()
    thread = watcher._thread  # pyright: ignore[reportPrivateUsage]  # internal access
    watcher.start()
    assert watcher._thread is thread  # pyright: ignore[reportPrivateUsage]  # internal access
    watcher.close()
    transport.close()


def test_transport_watcher_is_lazy_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving())
    transport = IndexerTransport("http://idx")
    assert transport._tx_watcher is None  # pyright: ignore[reportPrivateUsage]  # internal access
    first = transport.transaction_watcher()
    assert first is not None
    assert transport.transaction_watcher() is first
    transport.close()
    assert transport._tx_watcher is None  # pyright: ignore[reportPrivateUsage]  # internal access


def test_transport_watcher_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _failing_stream())
    transport = IndexerTransport("http://idx")
    with caplog.at_level(logging.WARNING, logger="ootle._sync._endpoints"):
        watcher = transport.transaction_watcher()
    transport.close()
    assert watcher is None
    assert any("transaction watcher unavailable" in r.getMessage() for r in caplog.records)
