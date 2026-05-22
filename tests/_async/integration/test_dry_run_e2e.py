"""End-to-end dry-run flow against a real LocalNet indexer.

Gated on the ``OOTLE_INDEXER_URL`` env var. Run with::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
        uv run pytest -m integration tests/_async/integration/test_dry_run_e2e.py
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


async def test_dry_run_estimates_fee(indexer_url: str) -> None:
    secret = OotleSecretKey.random(Network.LOCAL_NET)
    wallet = OotleWallet(LocalSigner(secret))
    async with AsyncOotleClient.connect(indexer_url, wallet=wallet) as client:
        unsigned = await client.faucet().take_funds().pay_fee(500).prepare()
        result = await client.send_dry_run(unsigned)
    assert result.estimated_fee > 0
    assert result.outcome is not None
