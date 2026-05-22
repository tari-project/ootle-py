"""bech32m address generation and parse round-trip against fixtures."""

from __future__ import annotations

from typing import Any

import pytest

from ootle._crypto import CryptoProvider
from ootle.errors import CryptoBridgeError


def _vectors(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    return corpus["vectors"]


@pytest.mark.parametrize("vector_index", range(6))
def test_generate_address_matches_recorded(
    crypto: CryptoProvider, addresses_corpus: dict[str, Any], vector_index: int
) -> None:
    vec = _vectors(addresses_corpus)[vector_index]
    addr = crypto.generate_ootle_address(
        bytes.fromhex(vec["owner_pk"]),
        bytes.fromhex(vec["view_pk"]),
        vec["network"],
        bytes.fromhex(vec["memo"]) if vec["memo"] else None,
    )
    assert addr == vec["address"]


@pytest.mark.parametrize("vector_index", range(6))
def test_parse_address_matches_recorded(
    crypto: CryptoProvider, addresses_corpus: dict[str, Any], vector_index: int
) -> None:
    vec = _vectors(addresses_corpus)[vector_index]
    parsed = crypto.parse_ootle_address(vec["address"])
    assert parsed.owner_key.hex() == vec["owner_pk"]
    assert parsed.view_key.hex() == vec["view_pk"]
    assert parsed.network == vec["network"]
    expected_memo = bytes.fromhex(vec["memo"]) if vec["memo"] else None
    assert parsed.memo == expected_memo


def test_parse_invalid_address_raises_crypto_bridge_error(
    crypto: CryptoProvider,
) -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        crypto.parse_ootle_address("not-a-valid-address")
    assert exc.value.context == "parse_ootle_address"
