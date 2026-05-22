"""Write-side mixin methods for :class:`OotleClient`.

Extracted into a sibling module to keep ``client.py`` under the 200-line
ceiling. The mixin assumes the subclass exposes ``wallet``, ``_crypto``,
``_transport``, and ``transaction_timeout`` attributes; the type stub
below declares them so Pyright stays strict-clean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._client_send import dry_run_for_client, seal_for_client, send_for_client

if TYPE_CHECKING:
    from ootle._sync._transport import IndexerTransport
    from ootle._sync._watcher import PendingTransaction
    from ootle._crypto import CryptoProvider
    from ootle._types.transaction import (
        DryRunResult,
        Transaction,
        TransactionRequest,
        UnsignedTransaction,
    )
    from ootle.wallet import OotleWallet


class ClientWritesMixin:
    """Mixin: seal / send / dry-run methods.

    The mixin declares the subclass-provided attributes as instance
    annotations so Pyright sees them; subclasses must initialise them.
    """

    wallet: OotleWallet | None
    transaction_timeout: float
    _crypto: CryptoProvider | None
    _transport: IndexerTransport

    def seal_transaction(self, request: UnsignedTransaction | TransactionRequest) -> Transaction:
        """Seal ``request`` with the wallet's default signer."""
        return seal_for_client(request, wallet=self.wallet, crypto=self._crypto)

    def send_transaction(self, sealed: Transaction) -> PendingTransaction:
        """Submit a sealed transaction. Returns a pending watcher handle."""
        return send_for_client(
            sealed,
            wallet=self.wallet,
            crypto=self._crypto,
            transport=self._transport,
            timeout=self.transaction_timeout,
        )

    def send_dry_run(self, request: UnsignedTransaction | TransactionRequest) -> DryRunResult:
        """Seal ``request`` and submit it as a dry-run."""
        return dry_run_for_client(
            request,
            wallet=self.wallet,
            crypto=self._crypto,
            transport=self._transport,
        )
