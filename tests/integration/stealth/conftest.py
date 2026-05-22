"""Fixtures for the stealth integration suite.

Every fixture short-circuits with ``pytest.skip`` when the env var it
depends on is missing — so ``pytest`` collection does not fail when the
indexer is unavailable, mirroring the pattern in ``tests/conftest.py``
for ``indexer_url``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ootle import (
    AsyncOotleClient,
    LocalSigner,
    Network,
    OotleSecretKey,
    OotleWallet,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

NETWORK = Network.LOCAL_NET


@pytest.fixture
def fresh_keypair() -> Callable[[], tuple[OotleSecretKey, OotleWallet]]:
    """Factory returning ``(secret, wallet)`` pairs on demand.

    Each call generates a fresh :class:`OotleSecretKey` and a wallet
    seeded with a single :class:`LocalSigner`. The secret is returned
    alongside the wallet so tests can grab the ``view_secret`` half
    without reaching into private signer state.
    """

    def _make() -> tuple[OotleSecretKey, OotleWallet]:
        secret = OotleSecretKey.random(NETWORK)
        return secret, OotleWallet(default=LocalSigner(secret))

    return _make


@pytest.fixture
async def stealth_client(
    indexer_url: str,
    fresh_keypair: Callable[[], tuple[OotleSecretKey, OotleWallet]],
) -> AsyncIterator[tuple[AsyncOotleClient, OotleWallet, OotleSecretKey]]:
    """Open an :class:`AsyncOotleClient` with WASM-backed stealth crypto.

    Returns ``(client, wallet, secret)`` so tests can use the wallet's
    default signer and the secret's view half in the same scope. The
    client and wallet both default to the singleton WASM provider for
    stealth crypto — no explicit wiring needed.
    """
    secret, wallet = fresh_keypair()
    async with AsyncOotleClient.connect(indexer_url, wallet=wallet) as client:
        yield client, wallet, secret
