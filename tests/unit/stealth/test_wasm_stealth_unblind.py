"""Real-WASM stealth provider: unblind_output and stealth_dh_secret.

``unblind_output`` decrypts an inbound UTXO; the blob has no encrypt
export, so the happy-path vector is a "known encryption" generated from
the Rust crypto crate (see ``tests/fixtures/stealth_unblind_vector.json``).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle.errors import CryptoBridgeError


def _body(vec: dict[str, Any], encrypted_data: str) -> str:
    """Build the StealthUnspentOutput body JSON the authorizer would ship."""
    return json.dumps(
        {
            "output": {
                "commitment": vec["commitment"],
                "sender_public_nonce": vec["sender_public_nonce"],
                "encrypted_data": encrypted_data,
                "minimum_value_promise": 0,
                "viewable_balance_proof": None,
            },
            "spend_condition": {"Signed": vec["sender_public_nonce"]},
            "tag": 0,
        }
    )


def test_unblind_output_round_trip(
    provider: WasmCryptoProvider, stealth_unblind_vector: dict[str, Any]
) -> None:
    vec = stealth_unblind_vector
    result = provider.unblind_output(
        commitment=bytes.fromhex(vec["commitment"]),
        output_body_json=_body(vec, vec["encrypted_data"]),
        view_secret=bytes.fromhex(vec["view_secret"]),
        skip_memo=False,
    )
    assert result.value == vec["value"]
    assert result.mask == bytes.fromhex(vec["mask"])
    assert result.memo is None


def test_unblind_output_decodes_memo(
    provider: WasmCryptoProvider, stealth_unblind_vector: dict[str, Any]
) -> None:
    vec = stealth_unblind_vector
    result = provider.unblind_output(
        commitment=bytes.fromhex(vec["commitment"]),
        output_body_json=_body(vec, vec["encrypted_data_with_memo"]),
        view_secret=bytes.fromhex(vec["view_secret"]),
        skip_memo=False,
    )
    assert result.value == vec["value"]
    assert result.memo is not None
    assert json.loads(result.memo.decode("utf-8")) == vec["memo_json"]


def test_unblind_output_skip_memo_drops_memo(
    provider: WasmCryptoProvider, stealth_unblind_vector: dict[str, Any]
) -> None:
    vec = stealth_unblind_vector
    result = provider.unblind_output(
        commitment=bytes.fromhex(vec["commitment"]),
        output_body_json=_body(vec, vec["encrypted_data_with_memo"]),
        view_secret=bytes.fromhex(vec["view_secret"]),
        skip_memo=True,
    )
    assert result.value == vec["value"]
    assert result.memo is None


def test_unblind_output_wrong_key_raises(
    provider: WasmCryptoProvider, stealth_unblind_vector: dict[str, Any]
) -> None:
    vec = stealth_unblind_vector
    with pytest.raises(CryptoBridgeError):
        provider.unblind_output(
            commitment=bytes.fromhex(vec["commitment"]),
            output_body_json=_body(vec, vec["encrypted_data"]),
            view_secret=bytes.fromhex(vec["mask"]),  # valid scalar, wrong key
            skip_memo=False,
        )


def test_stealth_dh_secret_is_deterministic(provider: WasmCryptoProvider) -> None:
    owner_secret, _ = provider.generate_keypair()
    _, public_nonce = provider.generate_keypair()
    first = provider.stealth_dh_secret(
        network_byte=16, owner_secret=owner_secret, public_nonce=public_nonce
    )
    second = provider.stealth_dh_secret(
        network_byte=16, owner_secret=owner_secret, public_nonce=public_nonce
    )
    assert len(first) == 32
    assert first == second


def test_stealth_dh_secret_rejects_invalid_network(provider: WasmCryptoProvider) -> None:
    owner_secret, public_nonce = provider.generate_keypair()
    with pytest.raises(CryptoBridgeError):
        provider.stealth_dh_secret(
            network_byte=0xFF, owner_secret=owner_secret, public_nonce=public_nonce
        )
