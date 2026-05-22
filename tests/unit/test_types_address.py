"""Address parse/from_keys round-trips against the recorded corpus."""

from __future__ import annotations

from typing import Any

import pytest

from ootle._crypto import CryptoProvider
from ootle._types.address import Address, ComponentAddress
from ootle._types.network import Network


def _vectors(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    return corpus["vectors"]


@pytest.mark.parametrize("vector_index", range(6))
def test_parse_round_trips_known_addresses(
    crypto: CryptoProvider, addresses_corpus: dict[str, Any], vector_index: int
) -> None:
    vec = _vectors(addresses_corpus)[vector_index]
    addr = Address.parse(vec["address"], crypto=crypto)
    assert addr.bech32m == vec["address"]
    assert addr.network == Network(vec["network"])
    assert addr.owner_pk.hex() == vec["owner_pk"]
    assert addr.view_pk.hex() == vec["view_pk"]
    expected_memo = bytes.fromhex(vec["memo"]) if vec["memo"] else None
    assert addr.memo == expected_memo


@pytest.mark.parametrize("vector_index", range(6))
def test_from_keys_matches_recorded(
    crypto: CryptoProvider, addresses_corpus: dict[str, Any], vector_index: int
) -> None:
    vec = _vectors(addresses_corpus)[vector_index]
    network = Network(vec["network"])
    memo = bytes.fromhex(vec["memo"]) if vec["memo"] else None
    addr = Address.from_keys(
        bytes.fromhex(vec["owner_pk"]),
        bytes.fromhex(vec["view_pk"]),
        network,
        memo,
        crypto=crypto,
    )
    assert addr.bech32m == vec["address"]
    assert addr.network is network
    assert addr.memo == memo


def test_address_is_frozen_and_hashable(
    crypto: CryptoProvider, addresses_corpus: dict[str, Any]
) -> None:
    a = Address.parse(_vectors(addresses_corpus)[0]["address"], crypto=crypto)
    b = Address.parse(_vectors(addresses_corpus)[0]["address"], crypto=crypto)
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b} == {a}


# Oracle recorded from a live Tari wallet's ``accounts.get_default`` response:
# the bech32m address it returns and the ``component_address`` it returns for
# the same account must agree with our pure-Python derivation.
_WALLET_ORACLE_ADDRESS = "otl_loc_1yt3fedkgh2uytz5gtmywayfx7my9ady0sj8sswxwrgnw9xd359dks8fwfzlcz6qqz5sjl6mdga8uhj48q0sypsetntw5gq50u0hnwcqy5efze"  # noqa: E501
_WALLET_ORACLE_COMPONENT = (
    "component_c98b29e777f71c82512ead48d3aa90317b08a407e5474fc78c3254a9eff4e8d5"
)


def test_to_component_address_matches_wallet_oracle(crypto: CryptoProvider) -> None:
    address = Address.parse(_WALLET_ORACLE_ADDRESS, crypto=crypto)
    assert address.to_component_address() == ComponentAddress(_WALLET_ORACLE_COMPONENT)


def test_to_component_address_is_deterministic_and_well_formed(
    crypto: CryptoProvider, addresses_corpus: dict[str, Any]
) -> None:
    address = Address.parse(_vectors(addresses_corpus)[0]["address"], crypto=crypto)
    component = address.to_component_address()
    assert component == address.to_component_address()
    assert component.startswith("component_")
    body = component.removeprefix("component_")
    assert len(body) == 64
    assert bytes.fromhex(body)  # valid hex
