"""Defensive parsing of indexer UTXO substate payloads for stealth inputs.

:func:`_unspent_output_for` reads cryptographic material (sender nonce,
encrypted data) off the engine ``Utxo`` substate and pairs it with the
caller-held commitment before feeding the balance proof, so a burnt or
unrecognised substate must fail loudly rather than silently mis-parse an
unrelated body. The engine ``OutputBody`` shape (``public_nonce``, no
commitment) differs from the send-side ``UnspentOutput`` — see
:func:`ootle._async._client_stealth_parse.parse_substate_utxo`.
"""

from __future__ import annotations

from typing import Any

import pytest

from ootle._async.stealth._authorizer_helpers import (
    _unspent_output_for,  # pyright: ignore[reportPrivateUsage]
)
from ootle._types.substate import Substate, SubstateId, UnknownSubstateValue
from ootle.errors import InvalidArgumentError


def _engine_utxo_substate(
    commitment_hex: str,
    public_nonce_hex: str = "22" * 32,
    encrypted_hex: str = "33" * 80,
) -> Substate:
    """Engine ``Utxo`` substate shape (``OutputBody``: ``public_nonce``, no commitment)."""
    body: dict[str, Any] = {
        "public_nonce": public_nonce_hex,
        "encrypted_data": encrypted_hex,
        "minimum_value_promise": 0,
        "viewable_balance": None,
    }
    inner = {"output": body, "spend_condition": {"Signed": "22" * 32}, "tag": 1}
    return Substate(
        id=SubstateId(opaque=f"utxo_resource_{commitment_hex}"),
        version=0,
        value=UnknownSubstateValue(
            discriminator="Utxo", raw={"Utxo": {"output": inner, "is_frozen": False}}
        ),
    )


def test_parses_engine_utxo_substate() -> None:
    """The engine body's ``public_nonce``/``encrypted_data`` plus the caller commitment."""
    commitment = b"\x11" * 32
    output = _unspent_output_for(_engine_utxo_substate("11" * 32), commitment)
    assert output.commitment == commitment
    assert output.sender_public_nonce == b"\x22" * 32
    assert output.encrypted_data.raw == b"\x33" * 80


def test_burnt_utxo_raises() -> None:
    """A burnt UTXO (no ``output`` payload) must fail loudly, not mis-parse."""
    sub = Substate(
        id=SubstateId(opaque="utxo_resource_" + "11" * 32),
        version=0,
        value=UnknownSubstateValue(
            discriminator="Utxo", raw={"Utxo": {"output": None, "is_frozen": False}}
        ),
    )
    with pytest.raises(InvalidArgumentError, match="burnt or not a parseable"):
        _unspent_output_for(sub, b"\x11" * 32)


def test_non_utxo_substate_raises() -> None:
    """A non-UTXO payload that happens to carry an ``output`` key must not parse.

    Guards against a parser that looks for ``output`` anywhere instead of
    requiring the ``Utxo`` envelope.
    """
    sub = Substate(
        id=SubstateId(opaque="utxo_resource_" + "11" * 32),
        version=0,
        value=UnknownSubstateValue(
            discriminator="Component", raw={"output": {"some": "unrelated body"}}
        ),
    )
    with pytest.raises(InvalidArgumentError, match="burnt or not a parseable"):
        _unspent_output_for(sub, b"\x11" * 32)
