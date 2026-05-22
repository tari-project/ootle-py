"""``AsyncStealthTransfer`` — shape, chaining, validation."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle._async.stealth.transfer import AsyncStealthTransfer
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.stealth import Output
from ootle._types.want_input import WantInput
from ootle.errors import InvalidArgumentError

from ._builder_helpers import (
    COMMITMENT,
    COMPONENT,
    RESOURCE,
    make_client,
    recipient_address,
)


async def test_constructor_initial_state(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    builder = AsyncStealthTransfer(client, RESOURCE)
    assert builder._state.resource == RESOURCE  # pyright: ignore[reportPrivateUsage]  # internal access
    assert builder._state.inputs_to_spend == {}  # pyright: ignore[reportPrivateUsage]  # internal access
    assert builder._state.revealed_input_amount == 0  # pyright: ignore[reportPrivateUsage]  # internal access
    assert builder._state.outputs == []  # pyright: ignore[reportPrivateUsage]  # internal access
    await client.aclose()


async def test_fluent_methods_return_self(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    recipient = recipient_address()
    out = Output(destination=recipient, amount=10, resource_address=RESOURCE)
    b = AsyncStealthTransfer(client, RESOURCE)
    assert b.spend_revealed_input(COMPONENT, 100) is b
    assert b.to_revealed_output(50) is b
    assert b.to_stealth_output(out) is b
    assert b.pay_fee_from_revealed(10) is b
    assert b.pay_fee_from_stealth(COMPONENT, 5) is b
    await client.aclose()


async def test_spend_stealth_input_registers_want_and_input(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    addr = recipient_address()
    b = AsyncStealthTransfer(client, RESOURCE).spend_stealth_input(addr, COMMITMENT)
    assert addr in b._state.inputs_to_spend  # pyright: ignore[reportPrivateUsage]  # internal access
    want_types = {type(w).__name__ for w in b._want_list}  # pyright: ignore[reportPrivateUsage]  # internal access
    assert "StealthCommitment" in want_types
    await client.aclose()


async def test_duplicate_stealth_input_raises(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    addr = recipient_address()
    b = AsyncStealthTransfer(client, RESOURCE).spend_stealth_input(addr, COMMITMENT)
    with pytest.raises(InvalidArgumentError):
        b.spend_stealth_input(addr, COMMITMENT)
    await client.aclose()


async def test_negative_amounts_rejected(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE)
    with pytest.raises(InvalidArgumentError):
        b.spend_revealed_input(COMPONENT, 0)
    with pytest.raises(InvalidArgumentError):
        b.to_revealed_output(-1)
    await client.aclose()


async def test_second_spend_revealed_input_raises(httpx_mock: HTTPXMock) -> None:
    """A stealth transfer has a single revealed-input slot; a second call is rejected."""
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE).spend_revealed_input(COMPONENT, 100)
    with pytest.raises(InvalidArgumentError):
        b.spend_revealed_input(COMPONENT, 50)
    # The first call's withdrawn bucket survives untouched.
    assert b._state.revealed_input_amount == 100  # pyright: ignore[reportPrivateUsage]  # internal access
    assert b._revealed_input_label is not None  # pyright: ignore[reportPrivateUsage]  # internal access
    body = b._builder.build_unsigned()  # pyright: ignore[reportPrivateUsage]  # internal access
    instrs = json.loads(body.json)["instructions"]
    puts = [i for i in instrs if "PutLastInstructionOutputOnWorkspace" in i]
    assert len(puts) == 1
    await client.aclose()


async def test_pay_fee_from_revealed_folds_into_revealed_output(httpx_mock: HTTPXMock) -> None:
    """The fee counts toward the revealed-output balance (Model B)."""
    client = await make_client(httpx_mock)
    b = (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 110)
        .to_revealed_output(100)
        .pay_fee_from_revealed(10)
    )
    assert b._state.revealed_output_amount == 110  # pyright: ignore[reportPrivateUsage]  # internal access
    await client.aclose()


async def test_with_builder_escape_hatch(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    b = AsyncStealthTransfer(client, RESOURCE)
    called: list[bool] = []

    def _mut(inner: object) -> object:
        called.append(True)
        return inner

    assert b.with_builder(_mut) is b  # pyright: ignore[reportArgumentType]  # intentional type mismatch under test
    assert called == [True]
    await client.aclose()


async def test_want_list_contains_stealth_commitment(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    addr = recipient_address()
    b = (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_stealth_input(addr, COMMITMENT)
        .to_revealed_output(1)
    )
    matches = [w for w in b._want_list if isinstance(w, WantInput.StealthCommitment)]  # pyright: ignore[reportPrivateUsage]  # internal access
    assert len(matches) == 1
    assert matches[0].commitment == COMMITMENT
    assert matches[0].resource == RESOURCE
    _ = TARI_TOKEN  # touch the constant
    await client.aclose()
