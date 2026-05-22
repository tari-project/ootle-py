"""``AsyncTransactionWatcher`` actor internals + transport wiring.

Hand-maintained (separate ``tests/_sync`` mirror; see ``scripts/unasync.py``).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, cast

import httpx
import pytest

import ootle._async._watcher._actor as actor_mod
from ootle._async._transport import AsyncIndexerTransport
from ootle._async._watcher import AsyncTransactionWatcher
from ootle._types.transaction import TransactionId
from tests._helpers.sse import fake_aconnect_sse

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

    async def __aenter__(self) -> object:
        raise httpx.ConnectError("refused")

    async def __aexit__(self, *_a: object) -> None:
        return None


def _serving(*events: tuple[str, str], keep_open: bool = True) -> Callable[..., object]:
    """A ``_open_sse_stream`` stand-in that always serves a fresh source of *events*."""

    def _open(*_a: object, **_k: object) -> object:
        return fake_aconnect_sse(list(events), keep_open=keep_open)

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


async def _watcher() -> tuple[AsyncIndexerTransport, AsyncTransactionWatcher]:
    transport = AsyncIndexerTransport("http://idx")
    return transport, AsyncTransactionWatcher(transport.client, transport.url)


async def test_dispatch_resolves_registered_future() -> None:
    transport, watcher = await _watcher()
    future = watcher.register(_TX)
    watcher._dispatch(_sse(*_commit_event()))  # pyright: ignore[reportPrivateUsage]  # internal access
    await transport.aclose()
    assert future.result() == "Commit"


async def test_dispatch_ignores_noise() -> None:
    transport, watcher = await _watcher()
    future = watcher.register(_TX)
    watcher._dispatch(_sse("OtherEvent", "{}"))  # pyright: ignore[reportPrivateUsage]  # internal access
    watcher._dispatch(_sse("TransactionFinalized", "not json"))  # pyright: ignore[reportPrivateUsage]  # internal access
    watcher._dispatch(_sse(*_commit_event("other_tx")))  # pyright: ignore[reportPrivateUsage]  # internal access
    await transport.aclose()
    assert not future.done()


async def test_register_is_idempotent_then_fresh_after_dispatch() -> None:
    transport, watcher = await _watcher()
    first = watcher.register(_TX)
    assert watcher.register(_TX) is first
    watcher._dispatch(_sse(*_commit_event()))  # pyright: ignore[reportPrivateUsage]  # internal access
    assert watcher.register(_TX) is not first
    watcher.unregister(_TX)
    await transport.aclose()


async def test_start_dispatches_via_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = await _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving(_commit_event()))
    future = watcher.register(_TX)
    await watcher.start()
    tag = await asyncio.wait_for(future, 1.0)
    await watcher.aclose()
    await transport.aclose()
    assert tag == "Commit"


async def test_start_propagates_connect_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = await _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _failing_stream())
    with pytest.raises(httpx.ConnectError):
        await watcher.start()
    await transport.aclose()


async def test_reconnects_after_stream_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = await _watcher()
    monkeypatch.setattr(actor_mod, "_RECONNECT_DELAY", 0.001)
    monkeypatch.setattr(
        actor_mod,
        "_open_sse_stream",
        _serving_sequence(
            fake_aconnect_sse([], keep_open=False),
            fake_aconnect_sse([_commit_event()], keep_open=True),
        ),
    )
    future = watcher.register(_TX)
    await watcher.start()
    tag = await asyncio.wait_for(future, 1.0)
    await watcher.aclose()
    await transport.aclose()
    assert tag == "Commit"


async def test_aclose_settles_outstanding(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = await _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving())
    future = watcher.register(_TX)
    await watcher.start()
    await watcher.aclose()
    await transport.aclose()
    assert future.cancelled()


async def test_start_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    transport, watcher = await _watcher()
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving())
    await watcher.start()
    task = watcher._task  # pyright: ignore[reportPrivateUsage]  # internal access
    await watcher.start()
    assert watcher._task is task  # pyright: ignore[reportPrivateUsage]  # internal access
    await watcher.aclose()
    await transport.aclose()


async def test_transport_watcher_is_lazy_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _serving())
    transport = AsyncIndexerTransport("http://idx")
    assert transport._tx_watcher is None  # pyright: ignore[reportPrivateUsage]  # internal access
    first = await transport.transaction_watcher()
    assert first is not None
    assert await transport.transaction_watcher() is first
    await transport.aclose()
    assert transport._tx_watcher is None  # pyright: ignore[reportPrivateUsage]  # internal access


async def test_transport_watcher_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _failing_stream())
    transport = AsyncIndexerTransport("http://idx")
    with caplog.at_level(logging.WARNING, logger="ootle._async._endpoints"):
        watcher = await transport.transaction_watcher()
    await transport.aclose()
    assert watcher is None
    assert any("transaction watcher unavailable" in r.getMessage() for r in caplog.records)
