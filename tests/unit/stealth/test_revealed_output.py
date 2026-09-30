"""``RevealedOutput`` — the receiver-bound revealed half of an outputs statement."""

from __future__ import annotations

import json

import pytest

from ootle._types.stealth import (
    RevealedOutput,
    StealthOutputsStatement,
    StealthTransferStatement,
)
from ootle._types.stealth._json import dumps_stable
from tests._helpers.stealth import REVEALED_RECEIVER


def test_stealth_outputs_statement_revealed_only_round_trip() -> None:
    stmt = StealthOutputsStatement.new_revealed_only(250, REVEALED_RECEIVER)
    encoded = stmt.to_json()
    assert encoded == {
        "outputs": [],
        "revealed_output": {"amount": 250, "receiver": REVEALED_RECEIVER.hex()},
        "agg_range_proof": "",
    }
    assert StealthOutputsStatement.from_json(encoded) == stmt
    assert stmt.revealed_output_amount == 250


def test_no_revealed_output_encodes_as_null() -> None:
    stmt = StealthOutputsStatement(outputs=(), revealed_output=None, agg_range_proof=b"")
    encoded = stmt.to_json()
    assert encoded["revealed_output"] is None
    assert stmt.revealed_output_amount == 0
    assert StealthOutputsStatement.from_json(encoded) == stmt


def test_revealed_output_accepts_string_amount() -> None:
    """The WASM blob serialises ``Amount`` as a JSON string."""
    parsed = RevealedOutput.from_json({"amount": "7", "receiver": REVEALED_RECEIVER.hex()})
    assert parsed == RevealedOutput(7, REVEALED_RECEIVER)


@pytest.mark.parametrize("amount", [0, -1])
def test_revealed_output_rejects_non_positive_amount(amount: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        RevealedOutput(amount, REVEALED_RECEIVER)


def test_revealed_output_rejects_short_receiver() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        RevealedOutput(1, b"\x01" * 31)


def test_stealth_transfer_statement_revealed_only_round_trip() -> None:
    s = StealthTransferStatement.revealed_only(300, 300, REVEALED_RECEIVER)
    assert s.balance_proof is None
    encoded = s.to_json()
    assert StealthTransferStatement.from_json(encoded) == s
    assert json.loads(dumps_stable(encoded))["balance_proof"] is None
