"""Shared scaffolding for stealth integration tests.

Helpers here keep individual test files focused on the behaviour they
assert. They never call ``pytest`` APIs directly — the suite stays
composable with ``await`` from any test function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle import (
    TARI,
    TARI_TOKEN,
    AsyncStealthTransfer,
    AsyncWalletStealthAuthorizer,
    Output,
    ResourceAddress,
    TransactionRequest,
)

if TYPE_CHECKING:
    from ootle import (
        Address,
        AsyncOotleClient,
        AsyncPendingTransaction,
        OotleWallet,
        StealthTransferSpec,
        TransactionOutcome,
    )


_TARI_RESOURCE = ResourceAddress(TARI_TOKEN)
DEFAULT_FAUCET_FEE: int = 1_000
DEFAULT_TRANSFER_FEE: int = 500


async def faucet_revealed(
    client: AsyncOotleClient,
    *,
    fee: int = DEFAULT_FAUCET_FEE,
) -> TransactionOutcome:
    """Faucet the dispensed-amount of XTR into the wallet's default account."""
    unsigned = await client.faucet().take_funds().pay_fee(fee).prepare()
    sealed = client.seal_transaction(unsigned)
    pending = await client.send_transaction(sealed)
    return await pending.watch()


async def faucet_stealth(
    client: AsyncOotleClient,
    wallet: OotleWallet,
    recipient: Address,
    *,
    stealth_amount: int,
    revealed_fee: int = DEFAULT_FAUCET_FEE,
) -> TransactionOutcome:
    """Faucet → stealth-deposit ``stealth_amount`` into ``recipient``."""
    statement = wallet.generate_outputs_statement(
        [Output(destination=recipient, amount=stealth_amount, resource_address=_TARI_RESOURCE)],
        revealed=revealed_fee,
    )
    unsigned = await (
        client.faucet()
        .take_funds()
        .take_funds_stealth(statement, pay_fees_from_revealed=True)
        .prepare()
    )
    sealed = client.seal_transaction(unsigned)
    pending = await client.send_transaction(sealed)
    return await pending.watch()


def stealth_transfer(
    client: AsyncOotleClient, *, resource: ResourceAddress = _TARI_RESOURCE
) -> AsyncStealthTransfer:
    """Sugar for :class:`AsyncStealthTransfer` against the TARI resource."""
    return AsyncStealthTransfer(client, resource)


async def send_stealth(
    client: AsyncOotleClient,
    wallet: OotleWallet,
    transfer: AsyncStealthTransfer,
    *,
    view_secret: bytes = b"\x00" * 32,
) -> tuple[StealthTransferSpec, AsyncPendingTransaction]:
    """Prepare → authorize → seal → submit a stealth transfer.

    Returns the (authorizer-hydrated) :class:`StealthTransferSpec` and
    the :class:`AsyncPendingTransaction` handle so tests can ``await
    pending.watch()`` and inspect the final outcome.
    """
    spec = await transfer.prepare()
    authorizer = AsyncWalletStealthAuthorizer(wallet, spec, view_secret=view_secret)
    hydrated = await authorizer.prepare(client)
    auths = await authorizer.create_authorizations(client)
    request = TransactionRequest(transaction=hydrated.unsigned).with_authorizations(auths)
    sealed = client.seal_transaction(request)
    pending = await client.send_transaction(sealed)
    return hydrated, pending


def tari(amount: int) -> int:
    """``amount`` TARI, expressed in the lowest-denomination units."""
    return amount * TARI
