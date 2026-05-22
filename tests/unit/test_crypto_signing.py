"""Schnorr signing through the WASM bridge.

Signing is randomised — we can't assert deterministic ``signature`` bytes.
We assert: the call succeeds; the returned ``public_nonce`` and
``signature`` are 32-byte buffers; calling twice with the same input
produces *different* nonces (high-confidence randomness sanity check).
"""

from __future__ import annotations

from typing import Any

import pytest

from ootle._crypto import CryptoProvider, SchnorrSignatureResult


@pytest.mark.parametrize("vector_index", range(3))
def test_schnorr_sign_returns_well_formed_signature(
    crypto: CryptoProvider, crypto_vectors: dict[str, Any], vector_index: int
) -> None:
    vec = crypto_vectors["vectors"]["schnorr_sign_inputs"][vector_index]
    sk = bytes.fromhex(vec["sk"])
    msg = bytes.fromhex(vec["message"])
    sig = crypto.schnorr_sign(sk, msg)
    assert isinstance(sig, SchnorrSignatureResult)
    assert len(sig.public_nonce) == 32
    assert len(sig.signature) == 32


def test_schnorr_sign_uses_fresh_nonce(
    crypto: CryptoProvider, crypto_vectors: dict[str, Any]
) -> None:
    vec = crypto_vectors["vectors"]["schnorr_sign_inputs"][0]
    sk = bytes.fromhex(vec["sk"])
    msg = bytes.fromhex(vec["message"])
    a = crypto.schnorr_sign(sk, msg)
    b = crypto.schnorr_sign(sk, msg)
    assert a.public_nonce != b.public_nonce
    assert a.signature != b.signature
