"""``ensure_max_epoch`` — the default validity window async builders stamp."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from ootle import AsyncOotleClient, TransactionBuilder
from ootle._async._max_epoch import ensure_max_epoch
from ootle._types._tx_body import DEFAULT_MAX_EPOCH_WINDOW

from ._helpers import mock_network


async def test_ensure_max_epoch_defaults_from_the_live_epoch(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock, epoch=7)
    builder = TransactionBuilder(0)
    async with AsyncOotleClient.connect("http://idx") as client:
        await ensure_max_epoch(client, builder)
    assert builder.max_epoch == 7 + DEFAULT_MAX_EPOCH_WINDOW


async def test_ensure_max_epoch_leaves_an_explicit_bound_alone(httpx_mock: HTTPXMock) -> None:
    mock_network(httpx_mock, epoch=7)
    builder = TransactionBuilder(0).with_max_epoch(3)
    async with AsyncOotleClient.connect("http://idx") as client:
        await ensure_max_epoch(client, builder)
    assert builder.max_epoch == 3
