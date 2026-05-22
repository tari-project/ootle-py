"""Spend a previously-acquired stealth UTXO end-to-end against LocalNet.

Round-trip: a stealth UTXO landed via faucet stealth deposit is then
spent in a follow-up transfer, whose inputs the wallet authorizer
hydrates from the sender's view secret. Stealth crypto runs on the
vendored ``ootle-wasm`` bridge (the default provider).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ootle import TARI_TOKEN, AsyncOotleClient, Output, ResourceAddress
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

    from ootle import OotleSecretKey, OotleWallet


async def test_spend_inbound_stealth_utxo(
    stealth_client: tuple[AsyncOotleClient, OotleWallet, OotleSecretKey],
    fresh_keypair: Callable[[], tuple[OotleSecretKey, OotleWallet]],
) -> None:
    """Deposit a stealth UTXO and then spend it in a follow-up transfer."""
    client, sender_wallet, sender_secret = stealth_client
    seed_outcome = await faucet_stealth(
        client,
        sender_wallet,
        sender_wallet.default_address,
        stealth_amount=tari(5),
    )
    assert seed_outcome.is_commit, f"seed faucet did not commit: {seed_outcome}"

    recipient_secret, _recipient_wallet = fresh_keypair()
    transfer = stealth_transfer(client)
    sender_account = sender_wallet.default_address.to_component_address()
    transfer.spend_revealed_input(sender_account, tari(3))
    transfer.to_stealth_output(
        Output(
            destination=recipient_secret.to_address(),
            amount=tari(2),
            resource_address=_TARI_RESOURCE,
        )
    )
    transfer.pay_fee_from_revealed(tari(1))

    _spec, pending = await send_stealth(
        client, sender_wallet, transfer, view_secret=sender_secret.view_secret
    )
    outcome = await pending.watch()
    assert outcome.is_commit, f"stealth spend did not commit: {outcome}"
