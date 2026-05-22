"""``AsyncStealthTransfer.prepare`` — happy-path provider flow."""

from __future__ import annotations

import json
from typing import Any, cast

from pytest_httpx import HTTPXMock

from ootle._async.stealth._spec import StealthTransferSpec
from ootle._async.stealth.transfer import AsyncStealthTransfer
from ootle._types.stealth import (
    Output,
    SignatureRequirements,
    StealthOutputsStatement,
)
from tests._helpers.instructions import kinds_and_methods

from ._builder_helpers import (
    COMMITMENT,
    COMPONENT,
    RESOURCE,
    make_client,
    recipient_address,
)


async def test_prepare_deposits_revealed_output_and_folds_fee(httpx_mock: HTTPXMock) -> None:
    """Fee folds into the revealed output; the bucket is deposited back (Model B)."""
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 110)
        .to_revealed_output(100)
        .pay_fee_from_revealed(10)
        .prepare()
    )
    assert isinstance(spec, StealthTransferSpec)
    # (a) the statement's revealed output includes the folded fee
    assert spec.statement.outputs_statement.revealed_output_amount == 110
    body: dict[str, Any] = json.loads(spec.unsigned.json)
    instructions: list[Any] = body["instructions"]
    kinds, methods = kinds_and_methods(instructions)
    assert "StealthTransfer" in kinds
    assert body["fee_instructions"]
    # (b) a deposit consumes the revealed-output bucket captured after the transfer
    assert "deposit" in methods
    st_idx = kinds.index("StealthTransfer")
    assert "PutLastInstructionOutputOnWorkspace" in kinds[st_idx + 1 :]
    await client.aclose()


async def test_prepare_must_sign_when_fee_from_revealed_without_revealed_input(
    httpx_mock: HTTPXMock,
) -> None:
    """``pay_fee_from_revealed`` draws on the account, so the account key must sign."""
    client = await make_client(httpx_mock)
    addr = recipient_address()
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_stealth_input(addr, COMMITMENT)
        .to_stealth_output(Output(destination=addr, amount=50, resource_address=RESOURCE))
        .pay_fee_from_revealed(10)
        .prepare()
    )
    assert spec.signature_requirements.must_sign_with_account_key()
    await client.aclose()


async def test_prepare_with_stealth_output_uses_provider_statement(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    recipient = recipient_address()
    out = Output(destination=recipient, amount=42, resource_address=RESOURCE)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 42)
        .to_stealth_output(out)
        .prepare()
    )
    body: dict[str, Any] = json.loads(spec.unsigned.json)
    instructions: list[Any] = body["instructions"]
    found: dict[str, Any] | None = None
    for ins in instructions:
        if not isinstance(ins, dict):
            continue
        ins_dict = cast("dict[str, Any]", ins)
        st = ins_dict.get("StealthTransfer")
        if isinstance(st, dict):
            found = cast("dict[str, Any]", st)
            break
    assert found is not None
    assert found["resource_address_ref"] == {"Address": RESOURCE}
    statement = found["statement"]
    assert isinstance(statement, dict)
    inputs_statement = cast("dict[str, Any]", statement["inputs_statement"])
    assert inputs_statement["revealed_amount"] == 42
    assert isinstance(spec.statement.outputs_statement, StealthOutputsStatement)
    await client.aclose()


async def test_prepare_signature_requirements_must_sign_when_revealed_in(
    httpx_mock: HTTPXMock,
) -> None:
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .prepare()
    )
    assert isinstance(spec.signature_requirements, SignatureRequirements)
    assert spec.signature_requirements.must_sign_with_account_key()
    await client.aclose()


async def test_prepare_signature_requirements_ephemeral_with_stealth_only(
    httpx_mock: HTTPXMock,
) -> None:
    client = await make_client(httpx_mock)
    addr = recipient_address()
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_stealth_input(addr, COMMITMENT)
        .to_revealed_output(100)
        .prepare()
    )
    assert not spec.signature_requirements.must_sign_with_account_key()
    await client.aclose()


async def test_prepare_revealed_input_emits_withdraw_and_workspace_label(
    httpx_mock: HTTPXMock,
) -> None:
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 50)
        .to_revealed_output(50)
        .prepare()
    )
    body: dict[str, Any] = json.loads(spec.unsigned.json)
    instructions: list[Any] = body["instructions"]
    methods: list[str] = []
    for ins in instructions:
        if not isinstance(ins, dict):
            continue
        ins_dict = cast("dict[str, Any]", ins)
        cm = ins_dict.get("CallMethod")
        if isinstance(cm, dict):
            method = cast("dict[str, Any]", cm).get("method")
            if isinstance(method, str):
                methods.append(method)
    assert "withdraw" in methods
    has_put = any(
        isinstance(ins, dict) and "PutLastInstructionOutputOnWorkspace" in ins
        for ins in instructions
    )
    assert has_put
    await client.aclose()


async def test_prepare_fee_from_stealth_emits_fee_instruction(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .pay_fee_from_stealth(COMPONENT, 25)
        .prepare()
    )
    body = json.loads(spec.unsigned.json)
    assert body["fee_instructions"]
    await client.aclose()


async def test_stealth_outputs_statement_result_is_propagated_in_spec(
    httpx_mock: HTTPXMock,
) -> None:
    """``StealthOutputsStatementResult`` flows into the assembled spec."""
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 123)
        .to_revealed_output(123)
        .prepare()
    )
    assert spec.statement.outputs_statement.revealed_output_amount == 123
    await client.aclose()
