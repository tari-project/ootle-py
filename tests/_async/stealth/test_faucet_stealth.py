"""``IAsyncFaucet.take_funds_stealth`` and the ``faucet_path`` helper."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pytest_httpx import HTTPXMock

from ootle._async.stealth.faucet_path import apply_take_funds_stealth
from ootle._transaction_builder import TransactionBuilder
from ootle._types.network import Network
from ootle._types.stealth import StealthTransferStatement
from ootle.errors import InvalidArgumentError

from ._builder_helpers import make_client


def _statement(revealed_input: int = 100) -> StealthTransferStatement:
    return StealthTransferStatement.revealed_only(revealed_input, revealed_input)


def test_apply_take_funds_stealth_requires_account_label() -> None:
    """Without a take_funds() prelude there is no account workspace to draw from."""
    builder = TransactionBuilder(Network.LOCAL_NET)
    with pytest.raises(InvalidArgumentError):
        apply_take_funds_stealth(
            builder,
            set(),
            account_label=None,
            statement=_statement(),
            pay_fees_from_revealed=True,
            bucket_label="__bucket",
            fee_bucket_label="__fee",
        )


async def test_take_funds_stealth_with_fees_from_revealed_emits_pay_fee_from_bucket(
    httpx_mock: HTTPXMock,
) -> None:
    client = await make_client(httpx_mock)
    statement = _statement()
    unsigned = await (
        client.faucet().take_funds().take_funds_stealth(statement, pay_fees_from_revealed=True)
    ).prepare()
    body: dict[str, Any] = json.loads(unsigned.json)
    fee_kinds = {
        next(iter(cast("dict[str, Any]", ins)))
        for ins in cast("list[Any]", body["fee_instructions"])
        if isinstance(ins, dict)
    }
    assert "PayFeeFromBucket" in fee_kinds
    await client.aclose()


async def test_take_funds_stealth_emits_stealth_instruction(httpx_mock: HTTPXMock) -> None:
    """End-to-end builder call: ``faucet().take_funds().take_funds_stealth(...)``."""
    client = await make_client(httpx_mock)
    statement = _statement()
    builder = client.faucet().take_funds().take_funds_stealth(statement)
    unsigned = await builder.prepare()
    body: dict[str, Any] = json.loads(unsigned.json)
    fee_instructions = cast("list[Any]", body["fee_instructions"])
    types_found = {
        next(iter(cast("dict[str, Any]", ins))) for ins in fee_instructions if isinstance(ins, dict)
    }
    assert "StealthTransfer" in types_found
    await client.aclose()


async def test_take_funds_stealth_without_take_funds_raises(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    with pytest.raises(InvalidArgumentError):
        client.faucet().take_funds_stealth(_statement())
    await client.aclose()


def _as_dict(value: object) -> dict[str, Any] | None:
    """Narrow a decoded-JSON value to a ``dict`` (cast keeps Pyright strict happy)."""
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _read_ids(instr: dict[str, Any]) -> list[int]:
    """Workspace ids an instruction *reads* (must already be on the workspace)."""
    kind = next(iter(instr))
    body = cast("dict[str, Any]", instr[kind])
    if kind == "CallMethod":
        ids: list[int] = []
        call = _as_dict(body["call"])
        if call is not None and "Workspace" in call:
            ids.append(int(call["Workspace"]))
        for raw in cast("list[Any]", body["args"]):
            arg = _as_dict(raw)
            ws = _as_dict(arg["Workspace"]) if arg is not None and "Workspace" in arg else None
            if ws is not None:
                ids.append(int(ws["id"]))
        return ids
    if kind == "StealthTransfer":
        bucket = _as_dict(body.get("revealed_input_bucket"))
        return [int(bucket["id"])] if bucket is not None else []
    if kind == "PayFeeFromBucket":
        return [int(cast("dict[str, Any]", body["bucket"])["id"])]
    if kind == "CreateAccount":
        bucket = _as_dict(body.get("bucket_workspace_id"))
        return [int(bucket["id"])] if bucket is not None else []
    return []


def _put_key(instr: dict[str, Any]) -> int | None:
    body = instr.get("PutLastInstructionOutputOnWorkspace")
    return None if body is None else int(cast("dict[str, Any]", body)["key"])


async def test_take_funds_stealth_workspace_ids_resolve_in_order(httpx_mock: HTTPXMock) -> None:
    """Every workspace reference must point to an already-put id.

    Regression: the faucet stealth path built its withdraw/stealth chain
    in an offset-merged inner builder, which rewrote the ``withdraw``'s
    account-workspace back-reference from id 0 to id 1. The engine then
    rejected execution with "Item at id 1 does not exist on the workspace
    (existing ids: [0])". Walk the fee instructions in execution order and
    assert no instruction reads a workspace id before it is put.
    """
    client = await make_client(httpx_mock)
    unsigned = await (
        client.faucet().take_funds().take_funds_stealth(_statement(), pay_fees_from_revealed=True)
    ).prepare()
    body: dict[str, Any] = json.loads(unsigned.json)
    available: set[int] = set()
    put_keys: list[int] = []
    for raw in cast("list[Any]", body["fee_instructions"]):
        instr = cast("dict[str, Any]", raw)
        for ref in _read_ids(instr):
            assert ref in available, f"{instr} reads unput workspace id {ref}"
        key = _put_key(instr)
        if key is not None:
            available.add(key)
            put_keys.append(key)
    assert put_keys == [0, 1, 2]
    await client.aclose()
