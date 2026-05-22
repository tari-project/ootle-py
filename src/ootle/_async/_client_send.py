"""Send-side helpers wrapping ``_send`` for :class:`AsyncOotleClient`.

Extracted into a sibling module to keep ``client.py`` under the 200-line
ceiling. The functions here are tightly coupled to the client surface —
they assume ``wallet`` and ``crypto`` are wired in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._send import require_wallet_and_crypto, seal_with_wallet, send_dry_run, send_sealed

if TYPE_CHECKING:
    from ootle._async._transport import AsyncIndexerTransport
    from ootle._async._watcher import AsyncPendingTransaction
    from ootle._crypto import CryptoProvider
    from ootle._types.transaction import (
        DryRunResult,
        Transaction,
        TransactionRequest,
        UnsignedTransaction,
    )
    from ootle.wallet import OotleWallet


def seal_for_client(
    request: UnsignedTransaction | TransactionRequest,
    *,
    wallet: OotleWallet | None,
    crypto: CryptoProvider | None,
) -> Transaction:
    """Seal ``request`` with the wallet's default signer."""
    wallet_, crypto_ = require_wallet_and_crypto(wallet, crypto)
    return seal_with_wallet(request, wallet=wallet_, crypto=crypto_)


async def send_for_client(
    sealed: Transaction,
    *,
    wallet: OotleWallet | None,
    crypto: CryptoProvider | None,
    transport: AsyncIndexerTransport,
    timeout: float,
) -> AsyncPendingTransaction:
    """Submit a sealed transaction. Returns a pending watcher handle."""
    _, crypto_ = require_wallet_and_crypto(wallet, crypto)
    return await send_sealed(sealed, transport=transport, crypto=crypto_, timeout=timeout)


async def dry_run_for_client(
    request: UnsignedTransaction | TransactionRequest,
    *,
    wallet: OotleWallet | None,
    crypto: CryptoProvider | None,
    transport: AsyncIndexerTransport,
) -> DryRunResult:
    """Seal ``request`` and submit it as a dry-run."""
    wallet_, crypto_ = require_wallet_and_crypto(wallet, crypto)
    return await send_dry_run(request, wallet=wallet_, transport=transport, crypto=crypto_)
