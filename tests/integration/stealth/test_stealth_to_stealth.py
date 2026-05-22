"""Stealth → stealth transfer coverage.

Two scenarios:

1. A single stealth recipient consumes the entire spendable amount.
2. A stealth recipient + revealed-change bucket for the sender.

Both run as fresh wallets seeded by a faucet stealth deposit so we
exercise the full path: spend stealth input → produce stealth output(s)
+ optional revealed change → fold balance proof → seal → finalise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ootle import TARI_TOKEN, Output, ResourceAddress
from tests.integration.stealth._helpers import (
    faucet_stealth,
    send_stealth,
    stealth_transfer,
    tari,
)

pytestmark = [pytest.mark.integration, pytest.mark.stealth]


_TARI_RESOURCE = ResourceAddress(TARI_TOKEN)


if TYPE_CHECKING:
    from collections.abc import Callable

    from ootle import AsyncOotleClient, OotleSecretKey, OotleWallet


async def test_stealth_to_stealth_single_recipient(
    stealth_client: tuple[AsyncOotleClient, OotleWallet, OotleSecretKey],
    fresh_keypair: Callable[[], tuple[OotleSecretKey, OotleWallet]],
) -> None:
    """A sender with revealed-only XTR funds a stealth output to a single recipient."""
    client, sender_wallet, _sender_secret = stealth_client
    recipient_secret, _recipient_wallet = fresh_keypair()
    recipient_address = recipient_secret.to_address()

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
    transfer.to_stealth_output(
        Output(destination=recipient_address, amount=tari(2), resource_address=_TARI_RESOURCE)
    )
    transfer.pay_fee_from_revealed(tari(1))

    _spec, pending = await send_stealth(client, sender_wallet, transfer)
    outcome = await pending.watch()
    assert outcome.is_commit, f"stealth → stealth transfer did not commit: {outcome}"


async def test_stealth_to_stealth_with_revealed_change(
    stealth_client: tuple[AsyncOotleClient, OotleWallet, OotleSecretKey],
    fresh_keypair: Callable[[], tuple[OotleSecretKey, OotleWallet]],
) -> None:
    """Stealth + revealed-change bucket — both outputs must land."""
    client, sender_wallet, _sender_secret = stealth_client
    recipient_secret, _recipient_wallet = fresh_keypair()
    recipient_address = recipient_secret.to_address()

    seed_outcome = await faucet_stealth(
        client,
        sender_wallet,
        sender_wallet.default_address,
        stealth_amount=tari(5),
    )
    assert seed_outcome.is_commit, f"seed faucet did not commit: {seed_outcome}"

    transfer = stealth_transfer(client)
    sender_account = sender_wallet.default_address.to_component_address()
    transfer.spend_revealed_input(sender_account, tari(4))
    transfer.to_stealth_output(
        Output(destination=recipient_address, amount=tari(1), resource_address=_TARI_RESOURCE)
    )
    transfer.to_revealed_output(tari(2))
    transfer.pay_fee_from_revealed(tari(1))

    _spec, pending = await send_stealth(client, sender_wallet, transfer)
    outcome = await pending.watch()
    assert outcome.is_commit, f"stealth → stealth + revealed-change did not commit: {outcome}"
