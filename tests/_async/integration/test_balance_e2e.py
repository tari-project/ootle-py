"""End-to-end read-only flow against a LocalNet indexer.

Marker-gated. Run with ``OOTLE_INDEXER_URL=... pytest -m integration``.
Skipped by default (``addopts`` includes ``-m 'not integration'``).

Mirrors the read-only slice of ``examples/balance_query.rs``:
1. ``get_network()`` returns a known :class:`Network`.
2. ``get_epoch()`` returns a positive int.
3. ``get_account_balances(account)`` returns a (possibly empty) dict —
   we don't assume a funded account; M4 will revisit with a faucet
   bootstrap.
"""

from __future__ import annotations

import os

import pytest

from ootle._async.client import AsyncOotleClient
from ootle._types.address import ComponentAddress
from ootle._types.network import Network

pytestmark = pytest.mark.integration


async def test_get_network_round_trips(indexer_url: str) -> None:
    async with AsyncOotleClient.connect(indexer_url) as client:
        network = await client.get_network()
    assert isinstance(network, Network)


async def test_get_epoch_returns_non_negative_int(indexer_url: str) -> None:
    async with AsyncOotleClient.connect(indexer_url) as client:
        epoch = await client.get_epoch()
    assert isinstance(epoch, int)
    assert epoch >= 0


async def test_get_account_balances_returns_a_dict(indexer_url: str) -> None:
    """Shape-only: we don't assume the account has any funds.

    If ``OOTLE_TEST_ACCOUNT`` is set, use that component address; else a
    fresh-looking one. Either way the indexer will return either a
    component substate or 404, and `get_account_balances` collapses
    both to a dict (possibly empty).
    """
    raw = os.environ.get("OOTLE_TEST_ACCOUNT", "component_" + "0" * 64)
    account = ComponentAddress(raw)
    async with AsyncOotleClient.connect(indexer_url) as client:
        balances = await client.get_account_balances(account)
    assert isinstance(balances, dict)
