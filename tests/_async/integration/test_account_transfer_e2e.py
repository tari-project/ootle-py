"""End-to-end single-signer account transfer against a real LocalNet indexer.

Gated on the ``OOTLE_INDEXER_URL`` env var (the ``indexer_url`` fixture
in :mod:`tests.conftest` skips the test when it is unset). Run with::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
        uv run pytest -m integration tests/_async/integration/test_account_transfer_e2e.py
"""

from __future__ import annotations

import pytest

from ootle import (
    TARI,
    AsyncOotleClient,
    LocalSigner,
    Network,
    OotleSecretKey,
    OotleWallet,
    ResourceAddress,
)
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ComponentAddress

pytestmark = pytest.mark.integration


async def test_account_transfer_e2e(indexer_url: str) -> None:
    sender_secret = OotleSecretKey.random(Network.LOCAL_NET)
    recipient_secret = OotleSecretKey.random(Network.LOCAL_NET)

    sender_wallet = OotleWallet(LocalSigner(sender_secret))
    async with AsyncOotleClient.connect(
        indexer_url, wallet=sender_wallet, transaction_timeout=120.0
    ) as client:
        # Fund the sender via the faucet.
        unsigned = await client.faucet().take_funds().pay_fee(500).prepare()
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        assert (await pending.with_timeout(120).watch()).is_commit

        # Transfer 2 TARI from sender to recipient.
        tari_resource = ResourceAddress(TARI_TOKEN)
        recipient_addr = recipient_secret.to_address()
        unsigned = await (
            client.account()
            .pay_fee(500)
            .public_transfer(recipient_addr, tari_resource, 2 * TARI)
            .prepare()
        )
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        assert (await pending.with_timeout(120).watch()).is_commit

        recipient_account = ComponentAddress(recipient_addr.bech32m)
        balance = await client.get_account_balance(recipient_account, tari_resource)
        assert balance >= 2 * TARI
