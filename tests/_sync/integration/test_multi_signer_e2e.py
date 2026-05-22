"""End-to-end multi-signer account transfer against a real LocalNet indexer.

Gated on the ``OOTLE_INDEXER_URL`` env var (the ``indexer_url`` fixture
in :mod:`tests.conftest` skips the test when it is unset). Run with::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
        uv run pytest -m integration tests/_async/integration/test_multi_signer_e2e.py
"""

from __future__ import annotations

import pytest

from ootle import (
    TARI,
    OotleClient,
    LocalSigner,
    Network,
    OotleSecretKey,
    OotleWallet,
    ResourceAddress,
    TransactionRequest,
)
from ootle._crypto import load_default_provider
from ootle._types._tari_constants import TARI_TOKEN

pytestmark = pytest.mark.integration


def test_multi_signer_e2e(indexer_url: str) -> None:
    a_secret = OotleSecretKey.random(Network.LOCAL_NET)
    b_secret = OotleSecretKey.random(Network.LOCAL_NET)
    recipient_secret = OotleSecretKey.random(Network.LOCAL_NET)

    # A seals; B co-authorises from a separate wallet so the seal step
    # does not double-sign B.
    wallet_a = OotleWallet(LocalSigner(a_secret))
    wallet_b = OotleWallet(LocalSigner(b_secret))

    with OotleClient.connect(indexer_url, wallet=wallet_a, transaction_timeout=120.0) as client:
        # Fund the sender via the faucet.
        unsigned = client.faucet().take_funds().pay_fee(500).prepare()
        sealed = client.seal_transaction(unsigned)
        pending = client.send_transaction(sealed)
        assert (pending.with_timeout(120).watch()).is_commit

        tari_resource = ResourceAddress(TARI_TOKEN)
        recipient_addr = recipient_secret.to_address()

        # Build the unsigned transaction.
        unsigned = (
            client.account()
            .pay_fee(500)
            .public_transfer(recipient_addr, tari_resource, 1 * TARI)
            .prepare()
        )
        # Co-signer B authorises.
        crypto = load_default_provider()
        auth_b = wallet_b.authorize(b_secret.to_address(), unsigned, crypto=crypto)
        # Default signer A seals + sends with B's authorisation folded in.
        request = TransactionRequest().with_transaction(unsigned).add_authorization(auth_b)
        sealed = client.seal_transaction(request)
        pending = client.send_transaction(sealed)
        outcome = pending.with_timeout(120).watch()
        assert outcome.is_commit
