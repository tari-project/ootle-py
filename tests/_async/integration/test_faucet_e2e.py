"""End-to-end faucet flow against a real LocalNet indexer.

Gated on the ``OOTLE_INDEXER_URL`` env var (the ``indexer_url`` fixture
in :mod:`tests.conftest` skips the test when it is unset). Run with::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
        uv run pytest -m integration tests/_async/integration/test_faucet_e2e.py
"""

from __future__ import annotations

import pytest

from ootle import (
    AsyncOotleClient,
    LocalSigner,
    Network,
    OotleSecretKey,
    OotleWallet,
)

pytestmark = pytest.mark.integration


async def test_faucet_e2e(indexer_url: str) -> None:
    secret = OotleSecretKey.random(Network.LOCAL_NET)
    wallet = OotleWallet(LocalSigner(secret))
    async with AsyncOotleClient.connect(
        indexer_url, wallet=wallet, transaction_timeout=120.0
    ) as client:
        unsigned = await client.faucet().take_funds().pay_fee(500).prepare()
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        outcome = await pending.with_timeout(120).watch()
        assert outcome.is_commit
        receipt = await pending.get_receipt()
        assert receipt is not None
