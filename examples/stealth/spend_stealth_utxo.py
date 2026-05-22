"""Spend an owned stealth UTXO (the input-aggregation path).

End-to-end round-trip exercising the headline stealth-spend features:

1. Faucet → stealth deposit to *self*, so the wallet owns a stealth UTXO
   (plus revealed change to pay fees with).
2. Discover the produced UTXO from the receipt diff and decrypt it with
   ``OotleWallet.decrypt_input_data`` (AEAD mask/value payload).
3. Spend it with ``AsyncStealthTransfer.spend_stealth_input``; the
   ``AsyncWalletStealthAuthorizer`` unblinds the input, aggregates the
   masks (``aggregate_input_masks``), and signs the balance proof.

The spend depends on the indexer/engine accepting the balance proof, so
this example reports the outcome rather than asserting — it is
informative either way.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.stealth.spend_stealth_utxo
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ootle import AsyncOotleClient, Output

from ._common import (
    TARI_RESOURCE,
    commitment_of,
    faucet_stealth,
    indexer_url,
    make_transfer,
    new_recipient,
    new_wallet,
    read_utxo_body,
    send_stealth,
    stealth_utxo_substate,
    tari,
    wait,
)

if TYPE_CHECKING:
    from ootle import AsyncPendingTransaction, OotleSecretKey, OotleWallet

SEED_AMOUNT = 5  # TARI deposited to self as a stealth UTXO, then spent in full
SPEND_FEE = 1  # TARI sourced from the faucet deposit's revealed change to pay the fee


async def _discover_and_decrypt(
    client: AsyncOotleClient,
    wallet: OotleWallet,
    secret: OotleSecretKey,
    pending: AsyncPendingTransaction,
) -> bytes | None:
    """Find the owned stealth UTXO, decrypt it, return its commitment."""
    substate = await stealth_utxo_substate(client, pending)
    if substate is None:
        print("no stealth UTXO substate found in the receipt diff")
        return None
    print(f"\nowned stealth UTXO: {substate.id.opaque}")

    body = read_utxo_body(substate)
    if body is None:
        return commitment_of(substate.id)
    commitment, nonce, encrypted = body
    decrypted = wallet.decrypt_input_data(
        commitment, encrypted, sender_public_nonce=nonce, view_secret=secret.view_secret
    )
    print(f"  decrypt_input_data  -> value={decrypted.value} µTari")
    return commitment


async def main() -> None:
    """Deposit a stealth UTXO to self, decrypt it, then spend it."""
    secret, wallet = new_wallet()
    sender_address = secret.to_address()
    sender_account = wallet.default_address.to_component_address()
    recipient = new_recipient()

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"owner:     {sender_address.bech32m}")
        print(f"recipient: {recipient.bech32m}")

        pending = await faucet_stealth(
            client, wallet, sender_address, stealth_amount=tari(SEED_AMOUNT)
        )
        if not (await wait("faucet-stealth", pending)).is_commit:
            print("seed faucet stealth deposit did not commit")
            return

        commitment = await _discover_and_decrypt(client, wallet, secret, pending)
        if commitment is None:
            return

        # Spend the stealth UTXO: spend_stealth_input pulls the input by
        # commitment; the authorizer unblinds it, aggregates the masks, and
        # signs the balance proof (input value == stealth output value). The
        # fee is covered by a small revealed input drawn from the account vault
        # (the change the faucet deposit left), so the confidential side stays
        # balanced: 5 stealth + 1 revealed in == 5 stealth + 1 fee out.
        transfer = make_transfer(client)
        transfer.spend_stealth_input(sender_address, commitment)
        transfer.spend_revealed_input(sender_account, tari(SPEND_FEE))
        transfer.to_stealth_output(
            Output(destination=recipient, amount=tari(SEED_AMOUNT), resource_address=TARI_RESOURCE)
        )
        transfer.pay_fee_from_revealed(tari(SPEND_FEE))

        _spec, spend = await send_stealth(client, wallet, transfer, view_secret=secret.view_secret)
        outcome = await wait("stealth-spend", spend)
        print(f"\nresult: {'committed' if outcome.is_commit else outcome.reason}")


if __name__ == "__main__":
    asyncio.run(main())
