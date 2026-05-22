"""``AsyncStealthTransfer.prepare`` — error paths and defensive checks."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from ootle import AsyncOotleClient
from ootle._async.stealth.transfer import AsyncStealthTransfer
from ootle._crypto._stealth_provider import StealthOutputsStatementResult
from ootle._types.stealth import Mask, StealthOutputsStatement
from ootle.errors import InvalidArgumentError
from tests._async._helpers import network_response
from tests._async.stealth._builder_helpers import (
    COMPONENT,
    RESOURCE,
    make_client,
    make_wallet,
)


async def test_prepare_requires_inputs(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE).to_revealed_output(100)
    with pytest.raises(InvalidArgumentError):
        await b.prepare()
    await client.aclose()


async def test_prepare_requires_outputs(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE).spend_revealed_input(COMPONENT, 100)
    with pytest.raises(InvalidArgumentError):
        await b.prepare()
    await client.aclose()


async def test_prepare_with_non_stealth_crypto_raises(httpx_mock: HTTPXMock) -> None:
    """A ``crypto=`` lacking the stealth surface fails the prepare guard."""
    client = await make_client(httpx_mock, crypto=object())
    b = (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
    )
    with pytest.raises(InvalidArgumentError):
        await b.prepare()
    await client.aclose()


async def test_prepare_rejects_unexpected_provider_result_shape(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())

    class _BadCrypto:
        def generate_outputs_statement(self, _specs: object, _revealed: int) -> object:
            return "not a result"

    client = await AsyncOotleClient.connect(
        "http://idx",
        wallet=make_wallet(),
        crypto=_BadCrypto(),  # pyright: ignore[reportArgumentType]  # intentional type mismatch under test
    ).open()
    b = (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 1)
        .to_revealed_output(1)
    )
    with pytest.raises(InvalidArgumentError):
        await b.prepare()
    await client.aclose()


def test_result_helper_constructs_stealth_outputs_result() -> None:
    """Smoke check on :class:`StealthOutputsStatementResult` typing."""
    res = StealthOutputsStatementResult(
        statement=StealthOutputsStatement.new_revealed_only(1),
        output_mask=Mask(raw=b"\x00" * 32),
    )
    assert res.statement.revealed_output_amount == 1
    assert res.output_mask.raw == b"\x00" * 32
