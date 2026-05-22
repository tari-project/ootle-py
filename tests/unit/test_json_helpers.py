"""``_types/_json.py`` — hex helpers and the outcome/event/receipt parsers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ootle._types._json import (
    bytes_to_hex,
    hex_to_bytes,
    parse_event,
    parse_receipt,
)
from ootle._types.substate import SubstateId

FIXTURES = Path(__file__).parent.parent / "fixtures" / "substate_examples"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_hex_round_trip() -> None:
    raw = b"\x00\x01\x10\xff"
    encoded = bytes_to_hex(raw)
    assert encoded == "000110ff"
    assert hex_to_bytes(encoded) == raw


def test_hex_to_bytes_tolerates_0x_prefix() -> None:
    assert hex_to_bytes("0xabcd") == b"\xab\xcd"
    assert hex_to_bytes("0Xabcd") == b"\xab\xcd"


def test_parse_event_minimal() -> None:
    ev = parse_event({"topic": "MyTpl::Sent"})
    assert ev.topic == "MyTpl::Sent"
    assert ev.payload == {}
    assert ev.template_address is None


def test_parse_event_full() -> None:
    ev = parse_event(
        {
            "topic": "X::Y",
            "payload": {"a": 1},
            "template_address": "tpl-1",
            "substate_id": "c-1",
        }
    )
    assert ev.template_address == "tpl-1"
    assert ev.substate_id == SubstateId(opaque="c-1")


_EMPTY_FEE_RECEIPT: dict[str, Any] = {
    "total_fee_payment": 0,
    "total_fees_paid": 0,
    "total_fee_overcharge": 0,
    "cost_breakdown": {"breakdown": {}},
}


def test_parse_receipt_round_trip() -> None:
    receipt = parse_receipt(_load("receipt.json"))
    assert receipt.epoch == 42
    assert receipt.fee_receipt.total_fee_payment == 500
    assert receipt.fee_receipt.total_fees_paid == 470
    # total_fees_charged is the engine-computed sum of the cost breakdown.
    assert receipt.fee_receipt.total_fees_charged == 500
    assert len(receipt.events) == 1
    assert receipt.events[0].topic == "MyTpl::Sent"
    assert receipt.logs == ("info: ok",)
    assert len(receipt.diff_summary.upped) == 1
    up = receipt.diff_summary.upped[0]
    assert up.substate_id.opaque.startswith("component_")
    assert up.version == 0
    assert up.value_hash.startswith("ffff")


def test_parse_receipt_missing_fee_receipt_raises() -> None:
    with pytest.raises(KeyError):
        parse_receipt({"epoch": 1})


def test_parse_receipt_rejects_bool_epoch() -> None:
    with pytest.raises(TypeError):
        parse_receipt({"epoch": True, "fee_receipt": _EMPTY_FEE_RECEIPT})
