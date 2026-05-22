"""``TransactionWatcher`` events-URL resolution (sync).

Hand-maintained sync mirror of ``tests/_async/test_watcher_url.py``.
"""

from __future__ import annotations

import httpx
import pytest

import ootle._sync._watcher._actor as actor_mod
from ootle._sync._transport import IndexerTransport
from ootle._sync._watcher import TransactionWatcher
from tests._helpers.sse import fake_connect_sse


def _capture(into: list[str]) -> object:
    def _open(_client: object, _method: object, url: str, *_a: object, **_k: object) -> object:
        into.append(url)
        return fake_connect_sse([], keep_open=True)

    return _open


def test_subscribes_to_absolute_events_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _capture(captured))
    # A caller-supplied client with no ``base_url`` cannot resolve a bare ``/events``.
    watcher = TransactionWatcher(httpx.Client(), "http://idx/")
    watcher.start()
    watcher.close()
    assert captured == ["http://idx/events"]


def test_url_built_from_transport_base(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(actor_mod, "_open_sse_stream", _capture(captured))
    transport = IndexerTransport("http://idx")
    watcher = transport.transaction_watcher()
    assert watcher is not None
    transport.close()
    assert captured == ["http://idx/events"]
