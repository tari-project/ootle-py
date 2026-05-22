"""End-to-end faucet → transfer example.

Python port of the public-path slice of
``ootle-rs/examples/fungible_transfer.rs``. Generates a fresh sender,
faucets TARI into it, registers a co-signer to exercise the multi-signer
path, dry-runs the transfer to surface the estimated fee, then transfers
2 TARI + 1 TARI to two freshly-generated recipients, watches each tx to
finalisation, and prints balances.

Self-contained: sender and recipients are generated on the fly, so the
only thing you need to run it is a reachable indexer.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.fungible_transfer
"""

from __future__ import annotations

import asyncio

from ootle import AsyncOotleClient, LocalSigner, OotleSecretKey

from ._common import (
    NETWORK,
    TARI_RESOURCE,
    faucet_and_wait,
    indexer_url,
    new_recipient,
    new_wallet,
    tari,
    wait,
)


async def main() -> None:
    sender_secret, wallet = new_wallet()
    sender_account = sender_secret.to_address().to_component_address()
    print(f"Sender address: {sender_secret.to_address().bech32m}")
    print(f"Sender account: {sender_account}")

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Network: {client.network.name}, epoch: {await client.get_epoch()}")

        # Step 1: faucet TARI into the sender's account.
        await faucet_and_wait(client)

        # Step 2: register a second signer to exercise the multi-signer
        # co-authorisation path (auto-fold at seal time).
        another_signer = OotleSecretKey.random(NETWORK)
        wallet.register(LocalSigner(another_signer))
        print(f"Registered co-signer: {another_signer.to_address().bech32m}")

        # Step 3: prepare the transfer (2 TARI + 1 TARI) to fresh recipients.
        recipient1 = new_recipient()
        recipient2 = new_recipient()
        unsigned = await (
            client.account()
            .pay_fee(1000)
            .public_transfer(recipient1, TARI_RESOURCE, tari(2))
            .public_transfer(recipient2, TARI_RESOURCE, tari(1))
            .prepare()
        )

        # Step 4: dry-run to estimate fees and surface any reject reason
        # before paying for the real send.
        dry_run = await client.send_dry_run(unsigned)
        outcome = dry_run.outcome
        if outcome is None or not outcome.is_commit:
            print(f"\nDry run did not commit: {outcome}")
            return
        print(f"\nDry run successful. Estimated fee: {dry_run.estimated_fee}")

        # Step 5: seal + send the real transfer.
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        await wait("transfer", pending)

        # Step 6: print balances.
        sender_balance = await client.get_account_balance(sender_account, TARI_RESOURCE)
        print(f"\nSender TARI balance: {sender_balance}")
        for label, addr in (("Recipient 1", recipient1), ("Recipient 2", recipient2)):
            balance = await client.get_account_balance(addr.to_component_address(), TARI_RESOURCE)
            print(f"{label} TARI balance: {balance}")


if __name__ == "__main__":
    asyncio.run(main())
