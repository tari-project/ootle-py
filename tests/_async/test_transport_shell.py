"""Transport shell — connection lifecycle + error mapping."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, NetworkError, TimeoutException
from pytest_httpx import HTTPXMock

from ootle._async._transport import AsyncIndexerTransport
from ootle.errors import IndexerClientError


async def test_request_round_trips(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/foo", json={"ok": True})
    async with AsyncIndexerTransport("http://idx") as transport:
        resp = await transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert resp is not None
    assert resp.json() == {"ok": True}


async def test_4xx_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/foo",
        status_code=400,
        text="bad request body",
    )
    async with AsyncIndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            await transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status == 400
    assert exc.value.body == "bad request body"
    assert exc.value.url == "http://idx/foo"


async def test_5xx_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/foo", status_code=503, text="busy")
    async with AsyncIndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            await transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status == 503


async def test_timeout_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(TimeoutException("timeout"))
    async with AsyncIndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            await transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status is None
    assert isinstance(exc.value.__cause__, TimeoutException)


async def test_network_error_maps_to_indexer_client_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(NetworkError("dns"))
    async with AsyncIndexerTransport("http://idx") as transport:
        with pytest.raises(IndexerClientError) as exc:
            await transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    assert exc.value.status is None
    assert isinstance(exc.value.__cause__, NetworkError)


async def test_user_supplied_client_is_not_closed() -> None:
    client = AsyncClient(base_url="http://idx")
    transport = AsyncIndexerTransport("http://idx", http_client=client)
    await transport.aclose()
    assert not client.is_closed
    await client.aclose()


async def test_owned_client_is_closed_by_aclose() -> None:
    transport = AsyncIndexerTransport("http://idx")
    client = transport._client  # pyright: ignore[reportPrivateUsage]  # internal access
    await transport.aclose()
    assert client.is_closed
