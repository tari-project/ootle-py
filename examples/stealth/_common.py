"""Shared scaffolding for the stealth examples.

Builds on the base example framework in :mod:`examples._common` (wallet
creation, faucet claims, the indexer-URL helper, ``wait``) and adds the
stealth-specific pieces: the ``prepare → authorize → seal → send`` dance
and stealth-UTXO discovery. It mirrors
``tests/integration/stealth/_helpers.py`` but is tuned for standalone
CLI runs against a LocalNet indexer.

Run any example with::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.stealth.<name>
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from examples._common import (
    TARI_RESOURCE,
    faucet,
    indexer_url,
    new_recipient,
    new_wallet,
    tari,
    wait,
)
from ootle import (
    AsyncStealthTransfer,
    AsyncWalletStealthAuthorizer,
    EncryptedData,
    Output,
    TransactionRequest,
)

if TYPE_CHECKING:
    from ootle import (
        Address,
        AsyncOotleClient,
        AsyncPendingTransaction,
        OotleWallet,
        StealthTransferSpec,
        Substate,
        SubstateId,
    )

__all__ = [
    "DEFAULT_FAUCET_FEE",
    "TARI_RESOURCE",
    "commitment_of",
    "faucet_revealed",
    "faucet_stealth",
    "indexer_url",
    "make_transfer",
    "new_recipient",
    "new_wallet",
    "read_utxo_body",
    "send_stealth",
    "stealth_utxo_substate",
    "tari",
    "wait",
]

DEFAULT_FAUCET_FEE = 1_000

# The indexer can emit the SSE "committed" event a beat before the full receipt
# diff is queryable, so reading the UTXO right after `watch()` occasionally races.
# Poll a few times before giving up.
_RECEIPT_RETRIES = 6
_RECEIPT_BACKOFF_S = 0.5


async def faucet_revealed(
    client: AsyncOotleClient, *, fee: int = DEFAULT_FAUCET_FEE
) -> AsyncPendingTransaction:
    """Claim the faucet's default dispense into the default account (revealed)."""
    return await faucet(client, fee=fee)


async def faucet_stealth(
    client: AsyncOotleClient,
    wallet: OotleWallet,
    recipient: Address,
    *,
    stealth_amount: int,
    revealed_fee: int = DEFAULT_FAUCET_FEE,
) -> AsyncPendingTransaction:
    """Faucet → stealth-deposit ``stealth_amount`` into ``recipient``.

    Demonstrates ``OotleWallet.generate_outputs_statement`` followed by
    ``IAsyncFaucet.take_funds_stealth`` — the public faucet stealth path.
    """
    statement = wallet.generate_outputs_statement(
        [Output(destination=recipient, amount=stealth_amount, resource_address=TARI_RESOURCE)],
        revealed=revealed_fee,
    )
    unsigned = await (
        client.faucet()
        .take_funds()
        .take_funds_stealth(statement, pay_fees_from_revealed=True)
        .prepare()
    )
    sealed = client.seal_transaction(unsigned)
    return await client.send_transaction(sealed)


def make_transfer(client: AsyncOotleClient) -> AsyncStealthTransfer:
    """Sugar for an :class:`AsyncStealthTransfer` over the TARI resource."""
    return AsyncStealthTransfer(client, TARI_RESOURCE)


async def send_stealth(
    client: AsyncOotleClient,
    wallet: OotleWallet,
    transfer: AsyncStealthTransfer,
    *,
    view_secret: bytes,
) -> tuple[StealthTransferSpec, AsyncPendingTransaction]:
    """Prepare → authorize → seal → submit ``transfer``.

    The :class:`AsyncWalletStealthAuthorizer` hydrates the balance proof
    (decrypting any stealth inputs with ``view_secret``) and signs each
    spent stealth input with its one-time spend key; those authorizations
    are folded into the request and the wallet's default signer seals.
    Returns the hydrated spec and the pending handle so callers can
    ``await wait(...)``.
    """
    spec = await transfer.prepare()
    authorizer = AsyncWalletStealthAuthorizer(wallet, spec, view_secret=view_secret)
    hydrated = await authorizer.prepare(client)
    auths = await authorizer.create_authorizations(client)
    request = TransactionRequest(transaction=hydrated.unsigned).with_authorizations(auths)
    sealed = client.seal_transaction(request)
    pending = await client.send_transaction(sealed)
    return hydrated, pending


async def stealth_utxo_substate(
    client: AsyncOotleClient, pending: AsyncPendingTransaction
) -> Substate | None:
    """Fetch the stealth UTXO substate produced by ``pending``.

    Reads the transaction receipt's diff summary for the produced
    ``utxo_…`` substate, then fetches it. The public client does not yet
    surface receipts, so we reach into the transport — a known v1 gap.
    Polls briefly because the receipt diff can lag the commit event.
    """
    for attempt in range(_RECEIPT_RETRIES):
        receipt = await client._transport.get_transaction_receipt(pending.tx_id)
        if receipt is not None:
            for up in receipt.diff_summary.upped:
                if up.substate_id.opaque.startswith("utxo_"):
                    return await client.fetch_substate(up.substate_id)
        if attempt + 1 < _RECEIPT_RETRIES:
            await asyncio.sleep(_RECEIPT_BACKOFF_S)
    return None


def commitment_of(substate_id: SubstateId) -> bytes:
    """Parse the 32-byte Pedersen commitment out of a ``utxo_…`` substate id."""
    return bytes.fromhex(substate_id.opaque.rsplit("_", 1)[-1])


def read_utxo_body(substate: Substate) -> tuple[bytes, bytes, EncryptedData] | None:
    """Pull ``(commitment, sender_public_nonce, encrypted_data)`` from a UTXO.

    The on-chain substate is the engine ``Utxo`` shape: ``OutputBody`` carries
    ``public_nonce`` + ``encrypted_data`` and **no** commitment (the commitment
    is derived and lives in the substate id). The Python ``Substate`` taxonomy
    does not decode the UTXO variant yet, so we walk the raw envelope.
    """
    raw = getattr(substate.value, "raw", None)
    if not isinstance(raw, dict):
        return None
    utxo = raw.get("Utxo") or raw.get("UTXO") or raw
    output_env = utxo.get("output") if isinstance(utxo, dict) else None
    body = output_env.get("output", output_env) if isinstance(output_env, dict) else None
    if not isinstance(body, dict):
        return None
    try:
        commitment = commitment_of(substate.id)
        nonce = bytes.fromhex(body["public_nonce"])
        encrypted = EncryptedData(raw=bytes.fromhex(body["encrypted_data"]))
    except (KeyError, TypeError, ValueError):
        return None
    return commitment, nonce, encrypted
