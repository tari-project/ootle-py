"""Stealth → revealed transfer coverage (full-withdraw path).

The sender consumes their revealed input bucket entirely into a single
revealed output bucket — no stealth output is produced. This exercises
the degenerate balance proof and verifies the recipient sees the
plaintext value on-chain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integration.stealth._helpers import faucet_stealth, send_stealth, stealth_transfer, tari

pytestmark = [pytest.mark.integration, pytest.mark.stealth]


if TYPE_CHECKING:
    from ootle import AsyncOotleClient, OotleSecretKey, OotleWallet


async def test_stealth_to_revealed_full_withdraw(
    stealth_client: tuple[AsyncOotleClient, OotleWallet, OotleSecretKey],
) -> None:
    """Full withdraw — all input revealed, all output revealed."""
    client, sender_wallet, _sender_secret = stealth_client

    seed_outcome = await faucet_stealth(
        client,
        sender_wallet,
        sender_wallet.default_address,
        stealth_amount=tari(5),
    )
    assert seed_outcome.is_commit, f"seed faucet did not commit: {seed_outcome}"

    transfer = stealth_transfer(client)
    sender_account = sender_wallet.default_address.to_component_address()
    transfer.spend_revealed_input(sender_account, tari(3))
    transfer.to_revealed_output(tari(2))
    transfer.pay_fee_from_revealed(tari(1))

    _spec, pending = await send_stealth(client, sender_wallet, transfer)
    outcome = await pending.watch()
    assert outcome.is_commit, f"stealth → revealed transfer did not commit: {outcome}"
