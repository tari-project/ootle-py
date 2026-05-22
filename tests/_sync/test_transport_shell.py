"""Transport shell — connection lifecycle + error mapping."""

from __future__ import annotations

import pytest
from httpx import Client, NetworkError, TimeoutException
from pytest_httpx import HTTPXMock

from ootle._sync._transport import IndexerTransport
from ootle.errors import IndexerClientError


def test_request_round_trips(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/foo", json={"ok": True})
    with IndexerTransport("http://idx") as transport:
        resp = transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert resp is not None
    assert resp.json() == {"ok": True}


def test_4xx_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/foo",
        status_code=400,
        text="bad request body",
    )
    with IndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status == 400
    assert exc.value.body == "bad request body"
    assert exc.value.url == "http://idx/foo"


def test_5xx_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/foo", status_code=503, text="busy")
    with IndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status == 503


def test_timeout_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(TimeoutException("timeout"))
    with IndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status is None
    assert isinstance(exc.value.__cause__, TimeoutException)


def test_network_error_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(NetworkError("dns"))
    with IndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status is None
    assert isinstance(exc.value.__cause__, NetworkError)


def test_user_supplied_client_is_not_closed() -> None:
    client = Client(base_url="http://idx")
    transport = IndexerTransport("http://idx", http_client=client)
    transport.close()
    assert not client.is_closed
    client.close()


def test_owned_client_is_closed_by_aclose() -> None:
    transport = IndexerTransport("http://idx")
    client = transport._client  # pyright: ignore[reportPrivateUsage]  # internal access
    transport.close()
    assert client.is_closed
