"""``AsyncOotleClient`` shell — connect / lifecycle / read-only queries."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from ootle._async.client import AsyncOotleClient
from ootle._types.network import Network
from ootle._types.substate import SubstateId
from ootle.errors import IndexerClientError

from ._helpers import mock_network


async def test_connect_warms_cached_network(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock)
    async with AsyncOotleClient.connect("http://idx") as client:
        assert client.network == Network.LOCAL_NET


async def test_async_with_closes_transport(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock)
    client = AsyncOotleClient.connect("http://idx")
    transport_client = client._transport._client  # pyright: ignore[reportPrivateUsage]  # internal access
    async with client:
        pass
    assert transport_client.is_closed


async def test_get_epoch_round_trips(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock, epoch=7)
    mock_network(httpx_mock, epoch=42)
    async with AsyncOotleClient.connect("http://idx") as client:
        assert await client.get_epoch() == 42


async def test_get_substate_raises_on_404(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock)
    httpx_mock.add_response(url="http://idx/substates/component_missing", status_code=404)
    async with AsyncOotleClient.connect("http://idx") as client:
        with pytest.raises(IndexerClientError):
            await client.get_substate(SubstateId("component_missing"))


async def test_fetch_substate_returns_none_on_404(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock)
    httpx_mock.add_response(url="http://idx/substates/component_missing", status_code=404)
    async with AsyncOotleClient.connect("http://idx") as client:
        assert await client.fetch_substate(SubstateId("component_missing")) is None
