"""``OotleSecretKey`` and ``OotlePublicKey`` behaviour."""

from __future__ import annotations

from ootle._crypto import CryptoProvider
from ootle._types.keys import OotlePublicKey, OotleSecretKey
from ootle._types.network import Network
from tests._helpers.crypto import MockCryptoProvider


def test_random_uses_provider_and_carries_network() -> None:
    mock = MockCryptoProvider()
    sk = OotleSecretKey.random(Network.LOCAL_NET, crypto=mock)
    assert sk.network == Network.LOCAL_NET
    assert len(sk.owner_secret) == 32
    assert len(sk.view_secret) == 32
    # Two consecutive `random` calls produce different keys (counter-driven mock):
    sk2 = OotleSecretKey.random(Network.LOCAL_NET, crypto=mock)
    assert sk2.owner_secret != sk.owner_secret


def test_random_with_real_bridge_produces_fresh_keys(crypto: CryptoProvider) -> None:
    a = OotleSecretKey.random(Network.LOCAL_NET, crypto=crypto)
    b = OotleSecretKey.random(Network.LOCAL_NET, crypto=crypto)
    assert a.owner_secret != b.owner_secret
    assert a.view_secret != b.view_secret


def test_repr_redacts_secret_bytes() -> None:
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\xff" * 32,
        view_secret=b"\xee" * 32,
    )
    text = repr(sk)
    assert "<32 bytes>" in text
    assert "Network.LOCAL_NET" in text
    assert "\\xff" not in text
    assert "\\xee" not in text


def test_public_keys_delegates_to_provider() -> None:
    mock = MockCryptoProvider()
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    pk = sk.public_keys(crypto=mock)
    expected_owner, expected_view = mock.ootle_public_key_from_secret(
        sk.owner_secret, sk.view_secret
    )
    assert pk == OotlePublicKey(owner_pk=expected_owner, view_pk=expected_view)


def test_to_address_uses_derived_public_keys() -> None:
    mock = MockCryptoProvider()
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    addr = sk.to_address(crypto=mock)
    assert addr.network == Network.LOCAL_NET
    assert addr.bech32m.startswith("otl_mock_")
    pk = sk.public_keys(crypto=mock)
    assert addr.owner_pk == pk.owner_pk
    assert addr.view_pk == pk.view_pk


def test_to_address_round_trips_through_real_bridge(crypto: CryptoProvider) -> None:
    sk = OotleSecretKey.random(Network.LOCAL_NET, crypto=crypto)
    addr = sk.to_address(crypto=crypto)
    assert addr.network == Network.LOCAL_NET
    assert addr.bech32m.startswith("otl_loc_")
    assert len(addr.owner_pk) == 32
    assert len(addr.view_pk) == 32


def test_secret_key_dataclass_equality() -> None:
    a = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    b = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    assert a == b
    assert hash(a) == hash(b)
