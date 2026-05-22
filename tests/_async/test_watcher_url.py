"""``AsyncTransactionWatcher`` events-URL resolution.

The watcher must subscribe against an absolute URL built from the
transport base, not a bare relative ``/events`` — a caller-supplied
``httpx`` client need not carry a ``base_url`` to resolve it against.
Hand-maintained (separate ``tests/_sync`` mirror; see ``scripts/unasync.py``).
"""

from __future__ import annotations

import httpx
import pytest

import ootle._async._watcher._actor as actor_mod
from ootle._async._transport import AsyncIndexerTransport
from ootle._async._watcher import AsyncTransactionWatcher
from tests._helpers.sse import fake_aconnect_sse


def _capture(into: list[str]) -> object:
    def _open(_client: object, _method: object, url: str, *_a: object, **_k: object) -> object:
        into.append(url)
        return fake_aconnect_sse([], keep_open=True)

    return _open


async def test_subscribes_to_absolute_events_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _capture(captured))
    # A caller-supplied client with no ``base_url`` cannot resolve a bare ``/events``.
    watcher = AsyncTransactionWatcher(httpx.AsyncClient(), "http://idx/")
    await watcher.start()
    await watcher.aclose()
    assert captured == ["http://idx/events"]


async def test_url_built_from_transport_base(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _capture(captured))
    transport = AsyncIndexerTransport("http://idx")
    watcher = await transport.transaction_watcher()
    assert watcher is not None
    await transport.aclose()
    assert captured == ["http://idx/events"]
