"""``create_stealth_authorizations`` — spend-signing a stealth input (sync surface).

Hand-written sync counterpart of
``tests/_async/stealth/test_authorizer_spend.py``. Covers the gap-#4 fix:
a spent stealth UTXO carries ``spend_condition: Signed(<one-time pk>)``,
so the transaction must carry a signature from that one-time key (never
the raw account key).
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING

import pytest

from ootle import LocalSigner, OotleSecretKey, OotleWallet
from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle._sync.stealth._authorizer_sign import create_stealth_authorizations
from ootle._sync.stealth._builder_helpers import StealthTransferState
from ootle._sync.stealth._spec import StealthTransferSpec
from ootle._sync.stealth.authorizer import WalletStealthAuthorizer
from ootle._sync.stealth.transfer import StealthTransfer
from ootle._types.network import Network
from ootle._types.stealth import (
    SignatureRequirements,
    StealthSignerRequirement,
    StealthTransferStatement,
)
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import InvalidArgumentError, KeyProviderNotFoundError

from ._builder_helpers import COMPONENT, RESOURCE, make_client

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

    from ootle._crypto import CryptoProvider
    from ootle._types.address import Address

_NONCE = b"\x07" * 32


def _spec(
    reqs: SignatureRequirements, *, unsigned_json: str = '{"instructions": []}'
) -> StealthTransferSpec:
    """A minimal spec carrying ``reqs`` — enough to drive the signing loop."""
    return StealthTransferSpec(
        unsigned=UnsignedTransaction(json=unsigned_json),
        statement=StealthTransferStatement.revealed_only(1, 1),
        signature_requirements=reqs,
        output_mask=None,
        state=StealthTransferState(resource=RESOURCE),
    )


def _wallet(provider: WasmCryptoProvider) -> tuple[OotleSecretKey, OotleWallet]:
    secret = OotleSecretKey.random(Network.LOCAL_NET, crypto=provider)
    return secret, OotleWallet(LocalSigner(secret))


def test_create_authorizations_signs_each_input_with_one_time_key(
    httpx_mock: HTTPXMock,
) -> None:
    """The produced authorization is signed by the one-time key, not the account key."""
    provider = WasmCryptoProvider.load_default()
    client = make_client(httpx_mock, crypto=provider)
    # A real revealed-only prepare yields a valid unsigned tx body to sign.
    spec0 = (
        StealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .prepare()
    )
    assert client.wallet is not None
    hydrated = WalletStealthAuthorizer.from_spec(client.wallet, spec0).prepare(client)

    secret, wallet = _wallet(provider)
    _, public_nonce = provider.generate_keypair()
    req = StealthSignerRequirement(signer=wallet.default_address, public_nonce=public_nonce)
    spec = dataclasses.replace(
        hydrated,
        signature_requirements=SignatureRequirements.new_must_sign_with_account_key((req,)),
    )

    auths = create_stealth_authorizations(wallet, spec, provider)

    assert len(auths) == 1
    sig = json.loads(auths[0].json)["signatures"][0]
    one_time = provider.stealth_dh_secret(
        Network.LOCAL_NET.value, secret.owner_secret, public_nonce
    )
    assert sig["public_key"] == provider.public_key_from_secret(one_time).hex()
    # Crucially NOT the raw account owner key — that is the whole bug.
    assert sig["public_key"] != secret.public_keys(crypto=provider).owner_pk.hex()
    client.close()


def test_create_authorizations_empty_for_revealed_only() -> None:
    """No stealth inputs ⇒ no authorizations to fold."""
    provider = WasmCryptoProvider.load_default()
    _, wallet = _wallet(provider)
    spec = _spec(SignatureRequirements.new_must_sign_with_account_key(()))
    assert create_stealth_authorizations(wallet, spec, provider) == ()


def test_create_authorizations_rejects_stealth_seal_signer() -> None:
    """Sealing with a one-time stealth key (no account-key seal) is unsupported."""
    provider = WasmCryptoProvider.load_default()
    _, wallet = _wallet(provider)
    req = StealthSignerRequirement(signer=wallet.default_address, public_nonce=_NONCE)
    spec = _spec(SignatureRequirements.new_opt_with_seal_signer((req,), None))
    with pytest.raises(NotImplementedError, match="one-time stealth key"):
        create_stealth_authorizations(wallet, spec, provider)


def test_create_authorizations_unknown_signer_raises() -> None:
    """A required signer with no registered key is an error."""
    provider = WasmCryptoProvider.load_default()
    _, wallet = _wallet(provider)
    stranger = OotleSecretKey.random(Network.LOCAL_NET, crypto=provider).to_address(crypto=provider)
    req = StealthSignerRequirement(signer=stranger, public_nonce=_NONCE)
    spec = _spec(SignatureRequirements.new_must_sign_with_account_key((req,)))
    with pytest.raises(KeyProviderNotFoundError):
        create_stealth_authorizations(wallet, spec, provider)


def test_create_authorizations_non_stealth_signer_raises() -> None:
    """A registered signer that cannot sign stealth inputs is rejected."""
    provider = WasmCryptoProvider.load_default()
    addr = OotleSecretKey.random(Network.LOCAL_NET, crypto=provider).to_address(crypto=provider)
    wallet = OotleWallet(_NonStealthSigner(addr))
    req = StealthSignerRequirement(signer=addr, public_nonce=_NONCE)
    spec = _spec(SignatureRequirements.new_must_sign_with_account_key((req,)))
    with pytest.raises(InvalidArgumentError, match="cannot sign stealth"):
        create_stealth_authorizations(wallet, spec, provider)


class _NonStealthSigner:
    """A bare :class:`Signer` with no stealth-signing capability."""

    def __init__(self, address: Address) -> None:
        self._address = address

    def address(self) -> Address:
        return self._address

    def add_signature(self, tx_json: str, seal_pk: bytes, *, crypto: CryptoProvider) -> str:
        return tx_json

    def seal(self, tx_json: str, *, crypto: CryptoProvider) -> str:
        return tx_json
