"""JSON parsing of the engine's stealth ``OutputBody`` substate shape."""

from __future__ import annotations

from ootle._types.stealth import StealthOutputBody


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
