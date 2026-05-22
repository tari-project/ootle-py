"""CBOR + JSON encoding round-trip tests for the instruction codec."""

from __future__ import annotations

import cbor2

from ootle._types._cbor import cbor_encode_amount
from ootle._types._tx_body import UnsignedTransactionV1Body
from ootle._types.address import ComponentAddress
from ootle._types.amount import TARI, Amount
from ootle._types.instructions import (
    CallMethod,
    ComponentRefAddress,
    InstructionArgLiteral,
    InstructionArgWorkspace,
    WorkspaceOffsetId,
    amount_literal,
)


def test_cbor_encode_amount_zero() -> None:
    encoded = cbor_encode_amount(Amount(0))
    decoded = cbor2.loads(encoded)
    assert decoded == [0, 0]


def test_cbor_encode_amount_small() -> None:
    encoded = cbor_encode_amount(Amount(1000))
    decoded = cbor2.loads(encoded)
    assert decoded == [1000, 0]


def test_cbor_encode_amount_above_u64() -> None:
    value = (1 << 64) + 7
    encoded = cbor_encode_amount(value)
    assert cbor2.loads(encoded) == [7, 1]


def test_amount_literal_round_trip() -> None:
    lit = amount_literal(10 * TARI)
    assert isinstance(lit, InstructionArgLiteral)
    body_bytes = bytes.fromhex(lit.body_hex)
    assert cbor2.loads(body_bytes) == [10 * TARI, 0]


def test_call_method_to_json() -> None:
    instr = CallMethod(
        call=ComponentRefAddress(address=ComponentAddress("component_abc")),
        method="take",
        args=(amount_literal(500),),
    )
    out = instr.to_json()
    assert "CallMethod" in out
    cm = out["CallMethod"]
    assert cm["call"] == {"Address": "component_abc"}
    assert cm["method"] == "take"
    assert len(cm["args"]) == 1
    assert "Literal" in cm["args"][0]


def test_workspace_arg_to_json() -> None:
    arg = InstructionArgWorkspace(workspace=WorkspaceOffsetId(id=2, offset=None))
    assert arg.to_json() == {"Workspace": {"id": 2, "offset": None}}


def test_unsigned_body_envelope_shape() -> None:
    body = UnsignedTransactionV1Body.empty(network=0x10)
    body.instructions.append(
        CallMethod(
            call=ComponentRefAddress(address=ComponentAddress("component_x")),
            method="m",
            args=(),
        )
    )
    out = body.to_json()
    assert out["network"] == 0x10
    assert out["fee_instructions"] == []
    assert len(out["instructions"]) == 1
    assert out["inputs"] == []
    assert out["min_epoch"] is None
    assert out["max_epoch"] is None
    assert out["is_seal_signer_authorized"] is True
    assert out["dry_run"] is False
