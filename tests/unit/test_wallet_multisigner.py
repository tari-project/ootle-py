"""``OotleWallet`` registration, default tracking, sealing, and errors."""

from __future__ import annotations

import pytest

from ootle._crypto import CryptoProvider
from ootle._signing import LocalSigner
from ootle._types.address import Address
from ootle._types.keys import OotleSecretKey
from ootle._types.network import Network
from ootle._types.transaction import (
    TransactionRequest,
    UnsignedTransaction,
)
from ootle.errors import (
    DefaultSignerNotSetError,
    InvalidArgumentError,
    KeyProviderNotFoundError,
)
from ootle.wallet import OotleWallet
from tests._helpers.crypto import MockCryptoProvider
from tests._helpers.signer import StubSigner


def _addr(crypto: CryptoProvider, marker: int) -> Address:
    """Build a synthetic Address through the (deterministic) mock bridge."""
    return Address.from_keys(
        owner_pk=bytes([marker]) * 32,
        view_pk=b"\x77" * 32,
        network=Network.LOCAL_NET,
        crypto=crypto,
    )


def test_construction_with_default_seeds_default_address() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    assert wallet.default_address == addr


def test_register_does_not_override_existing_default() -> None:
    crypto = MockCryptoProvider()
    addr_a = _addr(crypto, 0x01)
    addr_b = _addr(crypto, 0x02)
    wallet = OotleWallet(StubSigner(addr=addr_a, label="a"))
    wallet.register(StubSigner(addr=addr_b, label="b"))
    assert wallet.default_address == addr_a


def test_set_default_changes_default() -> None:
    crypto = MockCryptoProvider()
    addr_a = _addr(crypto, 0x01)
    addr_b = _addr(crypto, 0x02)
    wallet = OotleWallet(StubSigner(addr=addr_a, label="a"))
    wallet.register(StubSigner(addr=addr_b, label="b"))
    wallet.set_default(addr_b)
    assert wallet.default_address == addr_b


def test_signers_view_is_read_only() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    view = wallet.signers
    with pytest.raises(TypeError):
        view[addr] = StubSigner(addr=addr, label="x")  # pyright: ignore[reportIndexIssue]  # asserting read-only mapping rejects assignment


def test_default_address_raises_when_empty() -> None:
    wallet = OotleWallet()
    with pytest.raises(DefaultSignerNotSetError):
        _ = wallet.default_address


def test_set_default_unknown_raises_key_provider_not_found() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet()
    with pytest.raises(KeyProviderNotFoundError):
        wallet.set_default(addr)


def test_seal_with_no_transaction_raises_invalid_argument() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    with pytest.raises(InvalidArgumentError):
        wallet.seal(TransactionRequest(), crypto=crypto)


def test_seal_with_no_signers_raises_default_signer_not_set() -> None:
    crypto = MockCryptoProvider()
    request = TransactionRequest().with_transaction(UnsignedTransaction(json="tx"))
    wallet = OotleWallet()
    with pytest.raises(DefaultSignerNotSetError):
        wallet.seal(request, crypto=crypto)


def test_seal_calls_default_seal_only_for_single_signer() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    request = TransactionRequest().with_transaction(UnsignedTransaction(json="tx"))
    sealed = wallet.seal(request, crypto=crypto)
    assert sealed.json == "sealed(a):tx"


def test_seal_co_signs_then_seals_for_two_signers() -> None:
    crypto = MockCryptoProvider()
    addr_a = _addr(crypto, 0x01)
    addr_b = _addr(crypto, 0x02)
    wallet = OotleWallet(StubSigner(addr=addr_a, label="a"))
    wallet.register(StubSigner(addr=addr_b, label="b"))
    request = TransactionRequest().with_transaction(UnsignedTransaction(json="tx"))
    sealed = wallet.seal(request, crypto=crypto)
    # Default `a` seals; non-default `b` add_signatures first, committing
    # to `a`'s owner_pk as the seal_pk (regression for bug 01 — must NOT
    # be `b`'s own pk).
    assert sealed.json == "sealed(a):tx|sig(b,seal=01)"


def test_seal_passes_default_pk_not_signer_pk_as_seal_pk() -> None:
    """Regression for bug 01 (seal path).

    The auxiliary signer's ``add_signature`` must receive the *default*
    signer's owner_pk, not its own — otherwise the indexer rejects the
    envelope with "invalid signature".
    """
    crypto = MockCryptoProvider()
    addr_a = _addr(crypto, 0x01)
    addr_b = _addr(crypto, 0x02)
    wallet = OotleWallet(StubSigner(addr=addr_a, label="a"))
    wallet.register(StubSigner(addr=addr_b, label="b"))
    request = TransactionRequest().with_transaction(UnsignedTransaction(json="tx"))
    sealed = wallet.seal(request, crypto=crypto)
    assert "seal=01" in sealed.json
    assert "seal=02" not in sealed.json


def test_authorize_returns_authorization() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    auth = wallet.authorize(addr, UnsignedTransaction(json="tx"), crypto=crypto)
    assert auth.json == "tx|sig(a,seal=01)"


def test_authorize_commits_to_default_seal_pk() -> None:
    """Regression for bug 01 (authorize path).

    ``authorize`` must commit to the default signer's owner_pk, not the
    signer-being-authorised's pk.
    """
    crypto = MockCryptoProvider()
    addr_a = _addr(crypto, 0x01)
    addr_b = _addr(crypto, 0x02)
    wallet = OotleWallet(StubSigner(addr=addr_a, label="a"))
    wallet.register(StubSigner(addr=addr_b, label="b"))
    auth = wallet.authorize(addr_b, UnsignedTransaction(json="tx"), crypto=crypto)
    assert auth.json == "tx|sig(b,seal=01)"


def test_authorize_unknown_address_raises() -> None:
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet()
    with pytest.raises(KeyProviderNotFoundError):
        wallet.authorize(addr, UnsignedTransaction(json="tx"), crypto=crypto)


def test_local_signer_can_be_registered_with_real_bridge(
    crypto: CryptoProvider,
) -> None:
    """Smoke check: a real ``LocalSigner`` registers and exposes its address."""
    sk = OotleSecretKey.random(Network.LOCAL_NET, crypto=crypto)
    signer = LocalSigner(sk)
    wallet = OotleWallet(signer)
    assert wallet.default_address == signer.address()
    assert signer.address() in wallet.signers
