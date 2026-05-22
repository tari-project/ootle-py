"""Shared scaffolding for the runnable ootle examples.

Each example file demonstrates one feature; the repetitive setup —
indexer-URL resolution, wallet creation, faucet claims, the
``prepare → seal → send → watch`` dance, and new-substate extraction —
lives here so example files stay focused on the behaviour they show. The
stealth examples build on the same base (see
``examples/stealth/_common.py``).

Every helper targets a fresh LocalNet identity, so the examples are
self-contained: point them at a reachable indexer and run, no
pre-existing wallets or accounts required.

Run any example as a module from the repo root::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.<name>
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ootle import (
    TARI,
    TARI_TOKEN,
    LocalSigner,
    Network,
    OotleSecretKey,
    OotleWallet,
    ResourceAddress,
    default_indexer_url,
)

if TYPE_CHECKING:
    from ootle import (
        Address,
        AsyncOotleClient,
        AsyncPendingTransaction,
        DiffSummary,
        SubstateId,
        TransactionOutcome,
    )

__all__ = [
    "DEFAULT_FAUCET_FEE",
    "NETWORK",
    "TARI_RESOURCE",
    "faucet",
    "faucet_and_wait",
    "first_new_substate",
    "indexer_url",
    "new_recipient",
    "new_wallet",
    "tari",
    "wait",
]

NETWORK = Network.LOCAL_NET
TARI_RESOURCE = ResourceAddress(TARI_TOKEN)
DEFAULT_FAUCET_FEE = 500


def indexer_url() -> str:
    """Indexer URL from ``OOTLE_INDEXER_URL`` or the LocalNet default."""
    return os.environ.get("OOTLE_INDEXER_URL") or default_indexer_url(NETWORK)


def new_wallet() -> tuple[OotleSecretKey, OotleWallet]:
    """Generate a fresh ``(secret, wallet)`` pair for LocalNet."""
    secret = OotleSecretKey.random(NETWORK)
    return secret, OotleWallet(default=LocalSigner(secret))


def new_recipient() -> Address:
    """Generate a fresh recipient address (a throwaway account holder)."""
    return OotleSecretKey.random(NETWORK).to_address()


def tari(amount: int) -> int:
    """``amount`` TARI expressed in µTari (lowest-denomination units)."""
    return amount * TARI


def first_new_substate(
    diff: DiffSummary, prefix: str, *, exclude: set[str] | None = None
) -> SubstateId | None:
    """First ``<prefix>…`` upped substate id not already in *exclude*.

    Replaces the per-example ``_first_new_component`` / ``_first_new_template``
    helpers: pass ``"component_"`` or ``"template_"`` and read the returned
    id's ``.opaque`` to build the typed address.
    """
    excluded = exclude or set()
    for up in diff.upped:
        if up.substate_id.opaque.startswith(prefix) and up.substate_id.opaque not in excluded:
            return up.substate_id
    return None


async def wait(label: str, pending: AsyncPendingTransaction) -> TransactionOutcome:
    """Print the pending id, watch to finality, then print + return the outcome."""
    print(f"  pending {label}: {pending.tx_id}")
    outcome = await pending.watch()
    print(f"  finalized {label}: {outcome.kind}")
    return outcome


async def faucet(
    client: AsyncOotleClient, *, fee: int = DEFAULT_FAUCET_FEE
) -> AsyncPendingTransaction:
    """Claim the faucet's default dispense into the wallet's default account."""
    unsigned = await client.faucet().take_funds().pay_fee(fee).prepare()
    sealed = client.seal_transaction(unsigned)
    return await client.send_transaction(sealed)


async def faucet_and_wait(
    client: AsyncOotleClient, *, label: str = "faucet", fee: int = DEFAULT_FAUCET_FEE
) -> TransactionOutcome:
    """Faucet into the default account and watch the claim to finality."""
    return await wait(label, await faucet(client, fee=fee))
