"""Sealing + sending helpers — the M4 write-side flow.

Kept separate from ``client.py`` so the client surface stays thin (the
same pattern as ``_balances.py``). The orchestration here is the
Layer-1 mapping over Layer-3 (wallet) and Layer-6 (crypto bridge).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ootle._async._watcher import AsyncPendingTransaction
from ootle._types.transaction import (
    Transaction,
    TransactionRequest,
    UnsignedTransaction,
)
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._async._transport import AsyncIndexerTransport
    from ootle._crypto import CryptoProvider
    from ootle._types.transaction import DryRunResult
    from ootle.wallet import OotleWallet


def require_wallet_and_crypto(
    wallet: OotleWallet | None, crypto: CryptoProvider | None
) -> tuple[OotleWallet, CryptoProvider]:
    """Resolve a (wallet, crypto) pair or raise ``InvalidArgumentError``.

    Used by every write-side client method. ``crypto`` defaults to the
    process-wide singleton when ``None``.
    """
    if wallet is None:
        msg = "client has no wallet attached — cannot sign transactions"
        raise InvalidArgumentError(msg)
    if crypto is None:
        from ootle._crypto import load_default_provider  # noqa: PLC0415

        crypto = load_default_provider()
    return wallet, crypto


def seal_with_wallet(
    request: UnsignedTransaction | TransactionRequest,
    *,
    wallet: OotleWallet,
    crypto: CryptoProvider,
) -> Transaction:
    """Seal ``request`` using the wallet's default signer + folded auths.

    Mirrors Rust's ``TransactionRequest::build``: every authorization in
    the request is folded in, then the default signer seals.
    """
    if isinstance(request, UnsignedTransaction):
        request = TransactionRequest(transaction=request)
    if request.transaction is None:
        msg = "TransactionRequest.transaction is None — nothing to seal"
        raise InvalidArgumentError(msg)
    return wallet.seal(request, crypto=crypto)


async def send_sealed(
    sealed: Transaction,
    *,
    transport: AsyncIndexerTransport,
    crypto: CryptoProvider,
    timeout: float,
) -> AsyncPendingTransaction:
    """Encode ``sealed`` and submit; return a pending watcher handle.

    The indexer's ``/events`` SSE subscription is opened (once, lazily)
    *before* the transaction is submitted, so a fast finalisation cannot
    slip past the watcher between ``POST /transactions`` and ``watch()``.
    """
    envelope = crypto.bor_encode_transaction(sealed.json)
    watcher = await transport.transaction_watcher()
    tx_id = await transport.submit_transaction(envelope)
    return AsyncPendingTransaction(
        tx_id=tx_id, _transport=transport, _watcher=watcher, _timeout=timeout
    )


def _as_dry_run(json_body: str) -> str:
    """Return ``json_body`` with the ``dry_run`` flag forced on."""
    body: dict[str, Any] = json.loads(json_body)
    body["dry_run"] = True
    return json.dumps(body)


def mark_dry_run(
    request: UnsignedTransaction | TransactionRequest,
) -> UnsignedTransaction | TransactionRequest:
    """Force the ``dry_run`` flag on ``request``'s unsigned body.

    The indexer rejects a transaction posted to ``/transactions/dry-run``
    unless its ``dry_run`` flag is set, so :func:`send_dry_run` always
    applies this before sealing — callers need not set it themselves.
    """
    if isinstance(request, UnsignedTransaction):
        return UnsignedTransaction(json=_as_dry_run(request.json))
    if request.transaction is None:
        return request
    tx = UnsignedTransaction(json=_as_dry_run(request.transaction.json))
    return request.with_transaction(tx)


async def send_dry_run(
    request: UnsignedTransaction | TransactionRequest,
    *,
    wallet: OotleWallet,
    transport: AsyncIndexerTransport,
    crypto: CryptoProvider,
) -> DryRunResult:
    """Seal ``request`` and submit it as a dry-run.

    Note that the Rust upstream submits the *unsealed* dry-run transaction;
    we follow the indexer-friendly path here and seal first so the indexer
    sees a valid envelope. The ``dry_run`` flag is forced on the unsigned
    body via :func:`mark_dry_run` before sealing.
    """
    sealed = seal_with_wallet(mark_dry_run(request), wallet=wallet, crypto=crypto)
    envelope = crypto.bor_encode_transaction(sealed.json)
    return await transport.submit_transaction_dry_run(envelope)
