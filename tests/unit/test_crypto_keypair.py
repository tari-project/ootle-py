"""Keypair generation and derivation against the WASM bridge."""

from __future__ import annotations

from typing import Any

import pytest

from ootle._crypto import CryptoProvider


def test_generate_keypair_returns_two_32_byte_buffers(crypto: CryptoProvider) -> None:
    sk, pk = crypto.generate_keypair()
    assert len(sk) == 32
    assert len(pk) == 32
    assert sk != pk


def test_generate_ootle_secret_key_is_unique(crypto: CryptoProvider) -> None:
    a = crypto.generate_ootle_secret_key()
    b = crypto.generate_ootle_secret_key()
    assert a != b


@pytest.mark.parametrize(
    "vector_index",
    range(5),
    ids=lambda i: f"sk-{i}",
)
def test_public_key_from_secret_matches_recorded(
    crypto: CryptoProvider, crypto_vectors: dict[str, Any], vector_index: int
) -> None:
    vec = crypto_vectors["vectors"]["public_key_from_secret"][vector_index]
    derived = crypto.public_key_from_secret(bytes.fromhex(vec["sk"]))
    assert derived.hex() == vec["pk"]


@pytest.mark.parametrize(
    "vector_index",
    range(5),
    ids=lambda i: f"opk-{i}",
)
def test_ootle_public_key_from_secret_matches_recorded(
    crypto: CryptoProvider, crypto_vectors: dict[str, Any], vector_index: int
) -> None:
    vec = crypto_vectors["vectors"]["ootle_public_key_from_secret"][vector_index]
    owner_pk, view_pk = crypto.ootle_public_key_from_secret(
        bytes.fromhex(vec["owner_sk"]),
        bytes.fromhex(vec["view_sk"]),
    )
    assert owner_pk.hex() == vec["owner_pk"]
    assert view_pk.hex() == vec["view_pk"]
