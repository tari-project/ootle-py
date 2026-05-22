"""JSON round-trip coverage for every stealth value type.

Each test exercises ``from_json`` followed by ``to_json`` (or the
reverse) and asserts byte-stable behaviour: the output is the canonical
shape and the canonical serialiser (``dumps_stable``) yields stable
bytes across runs.
"""

from __future__ import annotations

import json
from typing import Any

from ootle._stealth_balance_proof import compact_statement_json
from ootle._types.stealth import (
    BalanceProofSignature,
    DecryptedData,
    EncryptedData,
    Mask,
    OneTimePublicKey,
    StealthInput,
    StealthInputsStatement,
    StealthOutputBody,
    StealthOutputsStatement,
    StealthTransferStatement,
    StealthUnspentOutput,
    UnspentOutput,
    ViewableBalanceProof,
)
from ootle._types.stealth._json import dumps_stable


def _hex(b: bytes) -> str:
    return b.hex()


def test_dumps_stable_is_byte_stable_for_dicts() -> None:
    """sort_keys + compact separators yield deterministic bytes."""
    payload: dict[str, Any] = {"b": 1, "a": [2, 3], "c": {"y": 4, "x": 5}}
    out = dumps_stable(payload)
    assert isinstance(out, bytes)
    assert out == b'{"a":[2,3],"b":1,"c":{"x":5,"y":4}}'
    # Repeated calls return the same bytes
    assert dumps_stable(payload) == out


def test_dumps_stable_rejects_round_trip_drift() -> None:
    """Two dicts with the same keys + values serialise identically."""
    a: dict[str, Any] = {"x": 1, "y": 2}
    b: dict[str, Any] = {"y": 2, "x": 1}
    assert dumps_stable(a) == dumps_stable(b)


def test_compact_statement_json_sorts_keys() -> None:
    """The balance-proof JSON helper sorts keys, so field reorders cannot drift it.

    The WASM ``generateStealthBalanceProofSignature`` export re-parses these
    strings before hashing (key order is wire-irrelevant), but the encoder must
    stay deterministic across runs and dataclass field reordering.
    """
    forward: dict[str, Any] = {"inputs": [{"b": 2, "a": 1}], "revealed_amount": 7}
    reversed_order: dict[str, Any] = {"revealed_amount": 7, "inputs": [{"a": 1, "b": 2}]}
    expected = '{"inputs":[{"a":1,"b":2}],"revealed_amount":7}'
    assert compact_statement_json(forward) == compact_statement_json(reversed_order) == expected


def test_mask_round_trip() -> None:
    raw = bytes(range(32))
    m = Mask(raw=raw)
    encoded = m.to_json()
    assert encoded == _hex(raw)
    assert Mask.from_json(encoded) == m


def test_one_time_public_key_round_trip() -> None:
    raw = b"\x07" * 32
    k = OneTimePublicKey(raw=raw)
    assert OneTimePublicKey.from_json(k.to_json()) == k


def test_encrypted_data_empty_round_trip() -> None:
    e = EncryptedData.empty()
    assert e.is_empty is True
    assert e.to_json() == ""
    assert EncryptedData.from_json("") == e


def test_encrypted_data_min_size_round_trip() -> None:
    # 80 bytes — ENCRYPTED_DATA_SIZE_WITHOUT_MEMO
    raw = bytes(range(80))
    e = EncryptedData(raw=raw)
    assert EncryptedData.from_json(e.to_json()) == e


def test_decrypted_data_round_trip_with_memo() -> None:
    d = DecryptedData(mask=b"\x01" * 32, value=42, memo=b"\xab\xcd")
    encoded = d.to_json()
    assert encoded == {"mask": "01" * 32, "value": 42, "memo": "abcd"}
    assert DecryptedData.from_json(encoded) == d


def test_decrypted_data_round_trip_without_memo() -> None:
    d = DecryptedData(mask=b"\x02" * 32, value=0, memo=None)
    assert DecryptedData.from_json(d.to_json()) == d


def test_balance_proof_signature_round_trip() -> None:
    sig = BalanceProofSignature(public_nonce=b"\x10" * 32, signature=b"\x20" * 32)
    assert BalanceProofSignature.from_json(sig.to_json()) == sig


def test_viewable_balance_proof_round_trip() -> None:
    vbp = ViewableBalanceProof(
        elgamal_encrypted=bytes(range(32)),
        elgamal_public_nonce=bytes(range(32, 64)),
        c_prime=bytes(range(64, 96)),
        e_prime=bytes(range(96, 128)),
        r_prime=bytes(range(128, 160)),
        s_v=bytes(range(160, 192)),
        s_m=bytes(range(192, 224)),
        s_r=bytes(range(224, 256)),
    )
    assert ViewableBalanceProof.from_json(vbp.to_json()) == vbp


def test_unspent_output_round_trip_without_vbp() -> None:
    encrypted = bytes(range(80))
    out = UnspentOutput(
        commitment=b"\xaa" * 32,
        sender_public_nonce=b"\xbb" * 32,
        encrypted_data=EncryptedData(raw=encrypted),
        minimum_value_promise=10,
        viewable_balance_proof=None,
    )
    assert UnspentOutput.from_json(out.to_json()) == out


def test_stealth_unspent_output_round_trip() -> None:
    encrypted = bytes(range(80))
    body = UnspentOutput(
        commitment=b"\xaa" * 32,
        sender_public_nonce=b"\xbb" * 32,
        encrypted_data=EncryptedData(raw=encrypted),
        minimum_value_promise=0,
        viewable_balance_proof=None,
    )
    suo = StealthUnspentOutput(output=body, spend_condition={"Signed": "ff" * 32}, tag=42)
    assert StealthUnspentOutput.from_json(suo.to_json()) == suo


def test_stealth_input_round_trip() -> None:
    inp = StealthInput(commitment=b"\xcc" * 32)
    assert StealthInput.from_json(inp.to_json()) == inp


def test_stealth_inputs_statement_round_trip_with_inputs() -> None:
    stmt = StealthInputsStatement(
        inputs=(StealthInput(commitment=b"\x01" * 32),),
        revealed_amount=100,
    )
    assert StealthInputsStatement.from_json(stmt.to_json()) == stmt


def test_stealth_inputs_statement_revealed_only() -> None:
    stmt = StealthInputsStatement.new_revealed_only(500)
    assert stmt.inputs == ()
    assert stmt.revealed_amount == 500
    assert StealthInputsStatement.from_json(stmt.to_json()) == stmt


def test_stealth_outputs_statement_revealed_only_round_trip() -> None:
    stmt = StealthOutputsStatement.new_revealed_only(250)
    encoded = stmt.to_json()
    assert encoded == {"outputs": [], "revealed_output_amount": 250, "agg_range_proof": ""}
    assert StealthOutputsStatement.from_json(encoded) == stmt


def test_stealth_transfer_statement_revealed_only_round_trip() -> None:
    s = StealthTransferStatement.revealed_only(300, 300)
    assert s.balance_proof is None
    encoded = s.to_json()
    # Byte-stable serialiser should accept either representation; compare
    # via round-trip rather than literal-byte equality so we are not
    # locking the entire payload byte-by-byte (covered in the dumps test).
    assert StealthTransferStatement.from_json(encoded) == s
    assert json.loads(dumps_stable(encoded))["balance_proof"] is None


def test_stealth_output_body_from_json_engine_shape() -> None:
    """The engine substate body uses ``public_nonce`` and no commitment."""
    body = StealthOutputBody.from_json(
        {
            "public_nonce": "aa" * 32,
            "encrypted_data": "00" * 80,
            "minimum_value_promise": 0,
            "viewable_balance": None,
        }
    )
    assert body.public_nonce == b"\xaa" * 32
    assert body.minimum_value_promise == 0
    assert body.viewable_balance is None


def test_stealth_output_body_parses_two_field_viewable_balance() -> None:
    """On-chain ``viewable_balance`` is the 2-field ElGamal ciphertext."""
    body = StealthOutputBody.from_json(
        {
            "public_nonce": "aa" * 32,
            "encrypted_data": "00" * 80,
            "minimum_value_promise": 5,
            "viewable_balance": {"encrypted": "bb" * 32, "public_nonce": "cc" * 32},
        }
    )
    assert body.viewable_balance is not None
    assert body.viewable_balance.encrypted == b"\xbb" * 32
    assert body.viewable_balance.public_nonce == b"\xcc" * 32


def test_stealth_transfer_statement_with_balance_proof_round_trip() -> None:
    bp = BalanceProofSignature(public_nonce=b"\xee" * 32, signature=b"\xff" * 32)
    inputs = StealthInputsStatement(
        inputs=(StealthInput(commitment=b"\x11" * 32),), revealed_amount=0
    )
    outputs = StealthOutputsStatement.new_revealed_only(0)
    transfer = StealthTransferStatement(
        inputs_statement=inputs, outputs_statement=outputs, balance_proof=bp
    )
    assert StealthTransferStatement.from_json(transfer.to_json()) == transfer
