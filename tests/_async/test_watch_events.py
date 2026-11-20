"""``client.watch_events`` — SSE subscription tests."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle import AsyncOotleClient
from ootle._async import _events as events_mod
from ootle._types.address import TemplateAddress
from ootle._types.events import TransactionEvent, TransactionEventFilter
from tests._helpers.encoded import encoded
from tests._helpers.sse import fake_aconnect_sse

from ._helpers import network_response

_NETWORK = network_response()


def _sse(topic: str, *, id: str = "1", template: str | None = None) -> tuple[str, str, str]:
    """Build a fake SSE event matching the indexer's wire shape."""
    inner: dict[str, object] = {"payload": {}}
    if template is not None:
        inner["template_address"] = template
    data = json.dumps({"transaction_id": "tx" + id, "event": encoded(inner)})
    return (topic, id, data)


async def test_watch_events_yields_matching_events(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    events_raw = [_sse("Counter::Inc", id="1"), _sse("Counter::Dec", id="2")]

    def _fake(_c: object, _m: object, _u: object, **_kw: object) -> object:
        return fake_aconnect_sse(events_raw)

    monkeypatch.setattr(events_mod, "_open_sse_stream", _fake)
    results: list[TransactionEvent] = []
    async with AsyncOotleClient.connect("http://idx") as client:
        async for e in client.watch_events():
            results.append(e)
    assert len(results) == 2
    assert results[0].topic == "Counter::Inc"
    assert results[0].id == 1
    assert results[0].transaction_id == "tx1"
    assert results[1].topic == "Counter::Dec"


async def test_watch_events_client_side_topic_filter(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    events_raw = [_sse("Counter::Inc"), _sse("Counter::Dec")]

    def _fake(_c: object, _m: object, _u: object, **_kw: object) -> object:
        return fake_aconnect_sse(events_raw)

    monkeypatch.setattr(events_mod, "_open_sse_stream", _fake)
    f = TransactionEventFilter(topic="Counter::Inc")
    results: list[TransactionEvent] = []
    async with AsyncOotleClient.connect("http://idx") as client:
        async for e in client.watch_events(f):
            results.append(e)
    assert len(results) == 1
    assert results[0].topic == "Counter::Inc"


async def test_watch_events_ignores_malformed_sse(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    undecodable = json.dumps({"transaction_id": "tx2", "event": "not-cbor!"})
    events_raw = [("bad", "1", "not-json"), ("bad", "2", undecodable), _sse("Good::Event")]

    def _fake(_c: object, _m: object, _u: object, **_kw: object) -> object:
        return fake_aconnect_sse(events_raw)

    monkeypatch.setattr(events_mod, "_open_sse_stream", _fake)
    results: list[TransactionEvent] = []
    async with AsyncOotleClient.connect("http://idx") as client:
        async for e in client.watch_events():
            results.append(e)
    assert len(results) == 1
    assert results[0].topic == "Good::Event"


async def test_watch_events_all_none_filter_passes_all(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    events_raw = [_sse("A::B")]

    def _fake(_c: object, _m: object, _u: object, **_kw: object) -> object:
        return fake_aconnect_sse(events_raw)

    monkeypatch.setattr(events_mod, "_open_sse_stream", _fake)
    results: list[TransactionEvent] = []
    async with AsyncOotleClient.connect("http://idx") as client:
        async for e in client.watch_events(TransactionEventFilter()):
            results.append(e)
    assert len(results) == 1


async def test_watch_events_normalizes_template_address_prefix(
    monkeypatch: pytest.MonkeyPatch, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    tmpl_hex = "ab" * 32
    events_raw = [
        _sse("Token::Mint", id="1", template=tmpl_hex),
        _sse("Token::Burn", id="2", template="cd" * 32),
    ]
    seen_params: list[object] = []

    def _fake(_c: object, _m: object, _u: object, **kw: object) -> object:
        seen_params.append(kw.get("params"))
        return fake_aconnect_sse(events_raw)

    monkeypatch.setattr(events_mod, "_open_sse_stream", _fake)
    f = TransactionEventFilter(template_address=TemplateAddress(f"template_{tmpl_hex}"))
    results: list[TransactionEvent] = []
    async with AsyncOotleClient.connect("http://idx") as client:
        async for e in client.watch_events(f):
            results.append(e)
    assert seen_params == [{"template_address": tmpl_hex}]
    assert [e.id for e in results] == [1]
