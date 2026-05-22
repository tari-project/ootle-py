"""Stealth → stealth transfer with revealed change.

A sender spends a revealed input and splits it into a confidential
output for a fresh recipient plus a revealed-change bucket for itself,
paying fees from its revealed vault. Both outputs must land.

Demonstrates ``AsyncStealthTransfer.to_stealth_output`` alongside
``to_revealed_output`` — the mixed confidential/revealed output shape.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.stealth.stealth_to_stealth
"""

from __future__ import annotations

import asyncio

from ootle import AsyncOotleClient, Output

from ._common import (
    TARI_RESOURCE,
    faucet_revealed,
    indexer_url,
    make_transfer,
    new_recipient,
    new_wallet,
    send_stealth,
    tari,
    wait,
)


async def main() -> None:
    """Faucet revealed funds, then split them into a stealth output + change."""
    sender_secret, sender_wallet = new_wallet()
    sender_account = sender_wallet.default_address.to_component_address()
    recipient = new_recipient()

    async with AsyncOotleClient.connect(indexer_url(), wallet=sender_wallet) as client:
        print(f"sender:    {sender_secret.to_address().bech32m}")
        print(f"recipient: {recipient.bech32m}")

        seed = await faucet_revealed(client)
        if not (await wait("faucet", seed)).is_commit:
            print("seed faucet did not commit")
            return

        transfer = make_transfer(client)
        transfer.spend_revealed_input(sender_account, tari(4))
        transfer.to_stealth_output(
            Output(destination=recipient, amount=tari(1), resource_address=TARI_RESOURCE)
        )
        transfer.to_revealed_output(tari(2))
        transfer.pay_fee_from_revealed(tari(1))

        _spec, pending = await send_stealth(
            client, sender_wallet, transfer, view_secret=sender_secret.view_secret
        )
        outcome = await wait("stealth->stealth", pending)
        print(f"\nresult: {'committed' if outcome.is_commit else outcome.reason}")


if __name__ == "__main__":
    asyncio.run(main())
