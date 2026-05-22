"""``AsyncOotleClient`` — crypto-provider wiring (WASM-only)."""

from __future__ import annotations

import pytest

from ootle._async._transport import AsyncIndexerTransport
from ootle._async.client import AsyncOotleClient
from ootle._crypto import CryptoProvider, load_default_provider


@pytest.fixture
def transport() -> AsyncIndexerTransport:
    return AsyncIndexerTransport("http://indexer.test")


@pytest.fixture
def wasm() -> CryptoProvider:
    return load_default_provider()


def test_constructor_without_crypto_defers_to_lazy_default(
    transport: AsyncIndexerTransport,
) -> None:
    """No ``crypto=`` leaves ``_crypto`` ``None`` — resolved to WASM lazily on use."""
    client = AsyncOotleClient(transport)
    assert client._crypto is None  # pyright: ignore[reportPrivateUsage]  # internal access


def test_constructor_with_custom_crypto_passes_through(
    transport: AsyncIndexerTransport,
    wasm: CryptoProvider,
) -> None:
    client = AsyncOotleClient(transport, crypto=wasm)
    assert client._crypto is wasm  # pyright: ignore[reportPrivateUsage]  # internal access


def test_connect_forwards_crypto(wasm: CryptoProvider) -> None:
    client = AsyncOotleClient.connect("http://indexer.test", crypto=wasm)
    assert client._crypto is wasm  # pyright: ignore[reportPrivateUsage]  # internal access


async def test_aclose_is_idempotent(transport: AsyncIndexerTransport) -> None:
    client = AsyncOotleClient(transport)
    await client.aclose()
    # ``aclose`` must not raise when called a second time.
    await client.aclose()
