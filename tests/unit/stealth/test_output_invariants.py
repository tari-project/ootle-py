"""Field invariants on :class:`Output`, :class:`Mask`, and friends.

The Rust upstream enforces these via ``NonZeroU64``, slice-length
checks, and assertions in ``Output::new`` / statement constructors.
We translate every one — fail-fast on bad shapes.
"""

from __future__ import annotations

from typing import Any

import pytest

from ootle._types.address import Address, ResourceAddress
from ootle._types.network import Network
from ootle._types.stealth import (
    EncryptedData,
    Mask,
    OneTimePublicKey,
    Output,
    StealthInput,
    StealthInputsStatement,
    StealthSignerRequirement,
    UnspentOutput,
    positive_amount,
)

_RESOURCE = ResourceAddress("resource_abc")


def _addr() -> Address:
    return Address(
        bech32m="otl_loc_dest",
        network=Network.LOCAL_NET,
        owner_pk=b"\x01" * 32,
        view_pk=b"\x02" * 32,
    )


def test_positive_amount_passes_through_positive_ints() -> None:
    assert positive_amount(1) == 1
    assert positive_amount(1_000_000) == 1_000_000


def test_positive_amount_rejects_zero_and_negative() -> None:
    with pytest.raises(ValueError, match="positive"):
        positive_amount(0)
    with pytest.raises(ValueError, match="positive"):
        positive_amount(-5)


def test_positive_amount_rejects_bool() -> None:
    with pytest.raises(TypeError):
        positive_amount(True)  # bool is int, but explicitly rejected


def test_output_rejects_zero_amount() -> None:
    with pytest.raises(ValueError, match="positive"):
        Output(destination=_addr(), amount=0, resource_address=_RESOURCE)


def test_output_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="positive"):
        Output(destination=_addr(), amount=-1, resource_address=_RESOURCE)


def test_output_rejects_negative_minimum_value_promise() -> None:
    with pytest.raises(ValueError, match="minimum_value_promise"):
        Output(
            destination=_addr(),
            amount=10,
            resource_address=_RESOURCE,
            minimum_value_promise=-1,
        )


def test_output_rejects_bad_resource_view_key_length() -> None:
    with pytest.raises(ValueError, match="resource_view_key"):
        Output(
            destination=_addr(),
            amount=10,
            resource_address=_RESOURCE,
            resource_view_key=b"\x00" * 5,
        )


def test_output_rejects_utxo_tag_out_of_range() -> None:
    with pytest.raises(ValueError, match="utxo_tag"):
        Output(
            destination=_addr(),
            amount=10,
            resource_address=_RESOURCE,
            utxo_tag=2**33,
        )


def test_output_defaults_match_rust() -> None:
    """Mirrors ``Output::new`` defaults: pay_to=StealthPublicKey, the rest None/0."""
    out = Output(destination=_addr(), amount=10, resource_address=_RESOURCE)
    assert out.resource_view_key is None
    assert out.memo is None
    assert out.pay_to == {"StealthPublicKey": {}}
    assert out.utxo_tag is None
    assert out.minimum_value_promise == 0


def test_output_from_json_defaults_pay_to_when_missing() -> None:
    """Absent ``pay_to`` falls back to the Rust default sentinel."""
    data: dict[str, Any] = {"resource_address": "resource_abc", "amount": 10}
    out = Output.from_json(data, destination=_addr())
    assert out.pay_to == {"StealthPublicKey": {}}


def test_output_from_json_preserves_explicit_empty_pay_to() -> None:
    """A present-but-empty ``pay_to: {}`` is preserved, not replaced by the
    default sentinel (item 09 — empty must not be conflated with missing)."""
    data: dict[str, Any] = {"resource_address": "resource_abc", "amount": 10, "pay_to": {}}
    out = Output.from_json(data, destination=_addr())
    assert out.pay_to == {}


def test_mask_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="Mask"):
        Mask(raw=b"\x00" * 31)


def test_one_time_public_key_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="OneTimePublicKey"):
        OneTimePublicKey(raw=b"\x00" * 31)


def test_encrypted_data_rejects_size_between_zero_and_minimum() -> None:
    with pytest.raises(ValueError, match="outside the allowed range"):
        EncryptedData(raw=b"\x00" * 10)


def test_encrypted_data_rejects_size_above_max() -> None:
    with pytest.raises(ValueError, match="outside the allowed range"):
        EncryptedData(raw=b"\x00" * 1000)


def test_stealth_input_rejects_wrong_commitment_length() -> None:
    with pytest.raises(ValueError, match="commitment"):
        StealthInput(commitment=b"\x00" * 31)


def test_stealth_inputs_statement_rejects_negative_revealed_amount() -> None:
    with pytest.raises(ValueError, match="revealed_amount"):
        StealthInputsStatement(inputs=(), revealed_amount=-1)


def test_stealth_inputs_statement_rejects_empty_inputs_with_zero_amount() -> None:
    """Mirrors Rust ``StealthInputsStatement::new`` assert at line 88."""
    with pytest.raises(ValueError, match="at least one input"):
        StealthInputsStatement(inputs=(), revealed_amount=0)


def test_signer_requirement_rejects_bad_public_nonce_length() -> None:
    with pytest.raises(ValueError, match="public_nonce"):
        StealthSignerRequirement(signer=_addr(), public_nonce=b"\x00" * 4)


def test_unspent_output_rejects_wrong_commitment_length() -> None:
    with pytest.raises(ValueError, match="commitment"):
        UnspentOutput(
            commitment=b"\x00" * 31,
            sender_public_nonce=b"\x00" * 32,
            encrypted_data=EncryptedData.empty(),
            minimum_value_promise=0,
        )


def test_unspent_output_rejects_negative_minimum_value_promise() -> None:
    with pytest.raises(ValueError, match="minimum_value_promise"):
        UnspentOutput(
            commitment=b"\x00" * 32,
            sender_public_nonce=b"\x00" * 32,
            encrypted_data=EncryptedData.empty(),
            minimum_value_promise=-1,
        )
