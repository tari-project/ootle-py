"""``LocalSigner`` Protocol satisfaction and delegation behaviour."""

from __future__ import annotations

from ootle._crypto import CryptoProvider
from ootle._signing import LocalSigner, Signer
from ootle._types.keys import OotleSecretKey
from ootle._types.network import Network
from tests._helpers.crypto import MockCryptoProvider


def _accept_signer(signer: Signer) -> Signer:
    return signer


def _accept_crypto(c: CryptoProvider) -> CryptoProvider:
    return c


def test_local_signer_satisfies_signer_protocol() -> None:
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    signer = LocalSigner(sk)
    _accept_signer(signer)


def test_local_signer_does_not_expose_secret() -> None:
    """The wrapped secret key must not be reachable through the public surface."""
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    signer = LocalSigner(sk)
    assert not hasattr(signer, "secret")


def test_mock_crypto_satisfies_crypto_provider_protocol() -> None:
    _accept_crypto(MockCryptoProvider())


def test_address_matches_secret_to_address(crypto: CryptoProvider) -> None:
    sk = OotleSecretKey.random(Network.LOCAL_NET, crypto=crypto)
    signer = LocalSigner(sk)
    assert signer.address() == sk.to_address(crypto=crypto)


def test_address_is_cached_after_first_call(crypto: CryptoProvider) -> None:
    sk = OotleSecretKey.random(Network.LOCAL_NET, crypto=crypto)
    signer = LocalSigner(sk)
    a1 = signer.address()
    a2 = signer.address()
    assert a1 is a2


def test_add_signature_delegates_to_crypto() -> None:
    mock = MockCryptoProvider()
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    signer = LocalSigner(sk)
    seal_pk = b"\x42" * 32
    out = signer.add_signature("tx-json", seal_pk, crypto=mock)
    # MockCryptoProvider returns a marker string embedding the inputs:
    assert out.startswith('{"prev":tx-json,"signer":"')
    # Calling again with the same inputs should produce the same marker:
    again = signer.add_signature("tx-json", seal_pk, crypto=mock)
    assert again == out


def test_add_signature_threads_seal_pk_through_to_bridge() -> None:
    """Regression: the seal_pk passed in is the one fed to the bridge.

    Before bug 01 was fixed, ``LocalSigner`` derived its own owner_pk
    and ignored what the wallet wanted to commit to. The bridge must
    see exactly the caller-supplied ``seal_pk``.
    """
    mock = MockCryptoProvider()
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    signer = LocalSigner(sk)
    # A pk that is *not* this signer's own — proves the param is honoured.
    seal_pk = b"\xab" * 32
    out_via_signer = signer.add_signature("tx-json", seal_pk, crypto=mock)
    out_direct = mock.add_transaction_signer("tx-json", sk.owner_secret, seal_pk)
    assert out_via_signer == out_direct
    # And the signer's own pk would produce a different marker — confirm.
    own_pk, _ = mock.ootle_public_key_from_secret(sk.owner_secret, sk.view_secret)
    assert own_pk != seal_pk
    assert out_via_signer != mock.add_transaction_signer("tx-json", sk.owner_secret, own_pk)


def test_seal_delegates_to_crypto() -> None:
    mock = MockCryptoProvider()
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x09" * 32,
        view_secret=b"\x08" * 32,
    )
    signer = LocalSigner(sk)
    out = signer.seal("tx-json", crypto=mock)
    expected = mock.seal_transaction("tx-json", sk.owner_secret)
    assert out == expected


def test_add_stealth_signature_derives_one_time_key_then_signs() -> None:
    """The stealth signature is produced by the one-time key, not the account key.

    ``add_stealth_signature`` must first derive the one-time spend secret
    via ``stealth_dh_secret`` (account secret + UTXO public nonce), then
    feed *that* secret — never the raw owner secret — to the bridge.
    """
    mock = MockCryptoProvider()
    sk = OotleSecretKey(
        network=Network.LOCAL_NET,
        owner_secret=b"\x01" * 32,
        view_secret=b"\x02" * 32,
    )
    signer = LocalSigner(sk)
    public_nonce = b"\x07" * 32
    seal_pk = b"\x42" * 32

    out = signer.add_stealth_signature("tx-json", public_nonce, seal_pk, crypto=mock)

    one_time = mock.stealth_dh_secret(Network.LOCAL_NET.value, sk.owner_secret, public_nonce)
    assert out == mock.add_transaction_signer("tx-json", one_time, seal_pk)
    # Signing with the raw account secret would produce a different marker.
    assert out != mock.add_transaction_signer("tx-json", sk.owner_secret, seal_pk)
