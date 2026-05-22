"""Stealth → revealed transfer (full withdraw).

The sender consumes a revealed input bucket entirely into a revealed
output bucket — no confidential output is produced. This exercises the
degenerate balance proof: the value lands on-chain in plaintext.

Demonstrates ``AsyncStealthTransfer.spend_revealed_input`` /
``to_revealed_output`` / ``pay_fee_from_revealed`` and the
``AsyncWalletStealthAuthorizer`` seal flow (see ``_common.send_stealth``).

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.stealth.stealth_to_revealed
"""

from __future__ import annotations

import asyncio

from ootle import AsyncOotleClient

from ._common import (
    faucet_revealed,
    indexer_url,
    make_transfer,
    new_wallet,
    send_stealth,
    tari,
    wait,
)


async def main() -> None:
    """Faucet revealed funds, then move them through a stealth transfer."""
    sender_secret, sender_wallet = new_wallet()
    sender_account = sender_wallet.default_address.to_component_address()

    async with AsyncOotleClient.connect(indexer_url(), wallet=sender_wallet) as client:
        print(f"sender: {sender_secret.to_address().bech32m}")

        seed = await faucet_revealed(client)
        if not (await wait("faucet", seed)).is_commit:
            print("seed faucet did not commit")
            return

        transfer = make_transfer(client)
        transfer.spend_revealed_input(sender_account, tari(3))
        transfer.to_revealed_output(tari(2))
        transfer.pay_fee_from_revealed(tari(1))

        _spec, pending = await send_stealth(
            client, sender_wallet, transfer, view_secret=sender_secret.view_secret
        )
        outcome = await wait("stealth->revealed", pending)
        print(f"\nresult: {'committed' if outcome.is_commit else outcome.reason}")


if __name__ == "__main__":
    asyncio.run(main())
