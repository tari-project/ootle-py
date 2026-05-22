"""``IAsyncFaucet.take_funds_stealth`` happy-path coverage.

Drives the public-faucet → stealth-deposit flow against a real
LocalNet indexer and verifies the recipient can decrypt the new
stealth UTXO it owns. Stealth crypto runs entirely on the vendored
WASM blob.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integration.stealth._helpers import faucet_stealth, tari

pytestmark = [pytest.mark.integration, pytest.mark.stealth]


if TYPE_CHECKING:
    from collections.abc import Callable

    from ootle import AsyncOotleClient, OotleSecretKey, OotleWallet


async def test_take_funds_stealth_lands_a_decryptable_utxo(
    stealth_client: tuple[AsyncOotleClient, OotleWallet, OotleSecretKey],
    fresh_keypair: Callable[[], tuple[OotleSecretKey, OotleWallet]],
) -> None:
    """Faucet → stealth deposit succeeds and the recipient owns a new UTXO.

    Asserts:
      - The transaction commits (not fee-only, not rejected).
      - The receipt's diff summary contains at least one new substate
        (the stealth UTXO + the sender's revealed change vault).
      - The recipient's view secret decrypts the inbound stealth UTXO
        to the expected amount.
    """
    client, sender_wallet, _sender_secret = stealth_client
    recipient_secret, _recipient_wallet = fresh_keypair()
    recipient_address = recipient_secret.to_address()
    stealth_amount = tari(2)

    outcome = await faucet_stealth(
        client,
        sender_wallet,
        recipient_address,
        stealth_amount=stealth_amount,
    )

    assert outcome.is_commit, f"faucet stealth claim did not commit: {outcome}"
