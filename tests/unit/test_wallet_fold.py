"""``OotleWallet`` authorization-folding behaviour (bug 02 regression).

Covers both the ``wallet.seal()`` orchestration that folds attached
``TransactionAuthorization``\\s and the underlying ``_fold_authorizations``
helper that handles the JSON splice.
"""

from __future__ import annotations

import json

from ootle._crypto import CryptoProvider
from ootle._types.address import Address
from ootle._types.network import Network
from ootle._types.transaction import (
    TransactionAuthorization,
    TransactionRequest,
    UnsignedTransaction,
)
from ootle._wallet_seal import fold_authorizations as _fold_authorizations
from ootle.wallet import OotleWallet
from tests._helpers.crypto import MockCryptoProvider
from tests._helpers.signer import StubSigner


def _addr(crypto: CryptoProvider, marker: int) -> Address:
    return Address.from_keys(
        owner_pk=bytes([marker]) * 32,
        view_pk=b"\x77" * 32,
        network=Network.LOCAL_NET,
        crypto=crypto,
    )


def test_seal_folds_authorizations_then_seals() -> None:
    """``seal()`` must splice each auth's signatures into the original body.

    Regression for bug 02 — earlier code overwrote ``tx_json`` with each
    authorisation's JSON, dropping the body and every prior signature.
    """
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    body = {"id": "tx-body"}
    auth_sig = {"public_key": "PK1", "signature": "SIG1"}
    request = (
        TransactionRequest()
        .with_transaction(UnsignedTransaction(json=json.dumps(body)))
        .add_authorization(
            TransactionAuthorization(
                json=json.dumps({"transaction": body, "signatures": [auth_sig]})
            )
        )
    )
    sealed = wallet.seal(request, crypto=crypto)
    assert sealed.json.startswith("sealed(a):")
    unsealed = json.loads(sealed.json.removeprefix("sealed(a):"))
    assert unsealed == {"transaction": body, "signatures": [auth_sig]}


def test_seal_merges_multiple_authorizations() -> None:
    """Multiple co-authorisations accumulate signatures in order."""
    crypto = MockCryptoProvider()
    addr = _addr(crypto, 0x01)
    wallet = OotleWallet(StubSigner(addr=addr, label="a"))
    body = {"id": "tx-body"}
    sig_b = {"public_key": "PK_B", "signature": "SIG_B"}
    sig_c = {"public_key": "PK_C", "signature": "SIG_C"}
    request = (
        TransactionRequest()
        .with_transaction(UnsignedTransaction(json=json.dumps(body)))
        .add_authorization(
            TransactionAuthorization(json=json.dumps({"transaction": body, "signatures": [sig_b]}))
        )
        .add_authorization(
            TransactionAuthorization(json=json.dumps({"transaction": body, "signatures": [sig_c]}))
        )
    )
    sealed = wallet.seal(request, crypto=crypto)
    unsealed = json.loads(sealed.json.removeprefix("sealed(a):"))
    assert unsealed["transaction"] == body
    assert unsealed["signatures"] == [sig_b, sig_c]


def test_fold_authorizations_empty_is_passthrough() -> None:
    """No authorisations → return the original tx JSON untouched."""
    tx = UnsignedTransaction(json='{"id":"tx"}')
    assert _fold_authorizations(tx, ()) == '{"id":"tx"}'


def test_fold_authorizations_preserves_body_and_appends_signatures() -> None:
    body = {"id": "tx-body", "instructions": ["foo"]}
    sig = {"public_key": "PK", "signature": "SIG"}
    tx = UnsignedTransaction(json=json.dumps(body))
    auth = TransactionAuthorization(json=json.dumps({"transaction": body, "signatures": [sig]}))
    folded = json.loads(_fold_authorizations(tx, (auth,)))
    assert folded == {"transaction": body, "signatures": [sig]}


def test_fold_authorizations_accumulates_across_multiple_auths() -> None:
    body = {"id": "tx"}
    sig1 = {"public_key": "A", "signature": "1"}
    sig2 = {"public_key": "B", "signature": "2"}
    tx = UnsignedTransaction(json=json.dumps(body))
    auths = (
        TransactionAuthorization(json=json.dumps({"transaction": body, "signatures": [sig1]})),
        TransactionAuthorization(json=json.dumps({"transaction": body, "signatures": [sig2]})),
    )
    folded = json.loads(_fold_authorizations(tx, auths))
    assert folded["signatures"] == [sig1, sig2]
