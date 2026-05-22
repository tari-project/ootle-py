"""Faucet → stealth deposit, then read the new UTXO back.

Demonstrates the public faucet stealth path and a read helper:

- ``OotleWallet.generate_outputs_statement`` + ``IAsyncFaucet.take_funds_stealth``
  deposit a confidential amount to a fresh recipient (see
  ``_common.faucet_stealth``).
- ``AsyncOotleClient.decrypt_owned_utxo`` decrypts the recipient's new UTXO
  with their view secret (AEAD owner-read), proving ownership of the value.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.stealth.faucet_deposit
"""

from __future__ import annotations

import asyncio

from ootle import AsyncOotleClient

from ._common import (
    faucet_stealth,
    indexer_url,
    new_wallet,
    stealth_utxo_substate,
    tari,
    wait,
)

STEALTH_AMOUNT = 2  # TARI


async def main() -> None:
    """Deposit a stealth amount to a fresh recipient and decrypt it back."""
    sender_secret, sender_wallet = new_wallet()
    recipient_secret, _recipient_wallet = new_wallet()
    recipient = recipient_secret.to_address()
    amount = tari(STEALTH_AMOUNT)

    async with AsyncOotleClient.connect(indexer_url(), wallet=sender_wallet) as client:
        print(f"sender:    {sender_secret.to_address().bech32m}")
        print(f"recipient: {recipient.bech32m}")

        pending = await faucet_stealth(client, sender_wallet, recipient, stealth_amount=amount)
        if not (await wait("faucet-stealth", pending)).is_commit:
            print("faucet stealth deposit did not commit")
            return

        substate = await stealth_utxo_substate(client, pending)
        if substate is None:
            print("no stealth UTXO substate found in the receipt diff")
            return
        print(f"\nstealth UTXO: {substate.id.opaque}")

        # The recipient decrypts the confidential value with their view secret.
        # This is the AEAD owner-read: the value + spend mask are recovered from
        # the output's encrypted_data — the way a recipient reads their own
        # inbound stealth UTXO.
        decrypted = await client.decrypt_owned_utxo(recipient_secret.view_secret, substate)
        if decrypted is None:
            print("could not decrypt the stealth UTXO")
            return
        print(f"recipient decrypts: {decrypted.value} µTari (expected {amount})")


if __name__ == "__main__":
    asyncio.run(main())
