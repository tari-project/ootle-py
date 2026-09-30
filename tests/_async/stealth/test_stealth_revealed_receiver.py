"""``AsyncStealthTransfer`` — the key authorised to take the revealed output."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from ootle._async.stealth.transfer import AsyncStealthTransfer
from ootle._types.stealth import Output, RevealedOutput
from ootle.errors import InvalidArgumentError
from tests._helpers.stealth import REVEALED_RECEIVER

from ._builder_helpers import COMPONENT, RESOURCE, make_client, recipient_address


async def test_unnamed_receiver_is_the_sealing_account_key(httpx_mock: HTTPXMock) -> None:
    """The default account key seals, so its badge is in the auth scope by construction."""
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .prepare()
    )
    expected = RevealedOutput(100, client.wallet.default_address.owner_pk)
    assert spec.statement.outputs_statement.revealed_output == expected
    await client.aclose()


async def test_named_receiver_wins_over_the_sealing_key(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(60, receiver=REVEALED_RECEIVER)
        .to_revealed_output(40)
        .prepare()
    )
    expected = RevealedOutput(100, REVEALED_RECEIVER)
    assert spec.statement.outputs_statement.revealed_output == expected
    await client.aclose()


async def test_no_revealed_output_resolves_to_none(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    out = Output(destination=recipient_address(), amount=100, resource_address=RESOURCE)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_stealth_output(out)
        .prepare()
    )
    assert spec.statement.outputs_statement.revealed_output is None
    await client.aclose()


async def test_revealing_zero_is_a_no_op(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE).to_revealed_output(0, receiver=REVEALED_RECEIVER)
    assert b._state.revealed_output_amount == 0  # pyright: ignore[reportPrivateUsage]  # internal access
    assert b._state.revealed_receiver is None  # pyright: ignore[reportPrivateUsage]  # internal access
    await client.aclose()


async def test_a_second_receiver_is_rejected(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE).to_revealed_output(1, receiver=REVEALED_RECEIVER)
    with pytest.raises(InvalidArgumentError, match="different receiver"):
        b.to_revealed_output(1, receiver=b"\x01" * 32)
    await client.aclose()


async def test_short_receiver_is_rejected(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    with pytest.raises(InvalidArgumentError, match="32 bytes"):
        AsyncStealthTransfer(client, RESOURCE).to_revealed_output(1, receiver=b"\x01")
    await client.aclose()
