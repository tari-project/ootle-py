"""Workspace piping + ``.then()`` escape hatch example.

Python port of the "Chaining with workspace piping" block in
``ootle-rs/examples/template_invoke.rs`` (lines 221-249), made
generic so it runs against any LocalNet indexer without a deployed
stable coin.

The killer composability feature of the transaction builder is
**bucket flow** — one instruction returns a ``Bucket``, the next
consumes it, all in the same atomic transaction. The pipe is the
named workspace slot::

    withdraw(...)                                   # returns Bucket
    put_last_instruction_output_on_workspace("b")   # stash it
    deposit(workspace("b"))                         # consume it

This example mirrors that pattern using the standard account
template's ``withdraw``/``deposit`` methods (already deployed on
every account), then drops down to the raw ``TransactionBuilder``
via ``.then()`` to add a ``create_account`` instruction that the
high-level :class:`~ootle.IAsyncComponent` doesn't expose.

Self-contained: all three accounts are generated and funded on the fly,
so the only thing you need to run it is a reachable indexer.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    uv run python -m examples.workspace_chain
"""

from __future__ import annotations

import asyncio
import sys

from ootle import Arg, AsyncOotleClient, LocalSigner, OotleSecretKey, args, workspace

from ._common import (
    NETWORK,
    TARI_RESOURCE,
    faucet_and_wait,
    indexer_url,
    new_wallet,
    tari,
    wait,
)

CHAIN_FEE = 2000


async def main() -> None:
    # Three keypairs:
    #   sender    — withdraws the bucket and pays fees.
    #   recipient — receives the bucket via deposit; account is pre-faucet'd
    #               so its substate exists when the deposit resolves.
    #   extra     — created from scratch inside the chain via .then() to
    #               demonstrate the escape hatch on the raw TransactionBuilder.
    sender, wallet = new_wallet()
    recipient = OotleSecretKey.random(NETWORK)
    extra = OotleSecretKey.random(NETWORK)
    sender_account = sender.to_address().to_component_address()
    recipient_account = recipient.to_address().to_component_address()
    extra_account = extra.to_address().to_component_address()
    print(f"Sender:    {sender_account}")
    print(f"Recipient: {recipient_account}")
    print(f"Extra:     {extra_account}")

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Network: {client.network.name}, epoch: {await client.get_epoch()}")

        # 1. Faucet the sender so it has TARI to withdraw + spend on fees.
        await faucet_and_wait(client, label="faucet sender")

        # 2. Faucet the recipient so its account substate exists. The
        #    deposit instruction requires the recipient component to be
        #    resolvable at execution time — without this preflight the
        #    chain would reject with "substate not found".
        wallet.register(LocalSigner(recipient))
        wallet.set_default(recipient.to_address())
        await faucet_and_wait(client, label="faucet recipient")
        wallet.set_default(sender.to_address())

        # 3. Build the workspace-piped chain. Three instructions plus an
        #    escape-hatch .then() — all four execute atomically.
        unsigned = await (
            client.component()
            # (a) withdraw returns a Bucket of TARI from the sender account.
            .call_method(
                sender_account,
                "withdraw",
                args=args(Arg.Address(TARI_RESOURCE), tari(2)),
            )
            # (b) capture the Bucket into workspace["bucket"].
            .put_last_instruction_output_on_workspace("bucket")
            # (c) deposit it into the recipient account.
            .call_method(
                recipient_account,
                "deposit",
                args=[workspace("bucket")],
            )
            # (d) escape hatch — drop down to the raw TransactionBuilder
            #     for an instruction the high-level builder doesn't expose
            #     (here, CreateAccount for a fresh empty account in the
            #     same atomic tx). The lambda receives the raw builder; any
            #     extra inputs it touches must be registered via
            #     .want_substate / .want_vault_for on the parent.
            .then(lambda b: b.create_account(extra.to_address().owner_pk))
            .pay_fee(CHAIN_FEE)
            .prepare()
        )
        print(f"\nChain tx JSON:\n{unsigned.json}\n")

        # 4. Dry-run first to surface estimated fees and any reject reason.
        dry_run = await client.send_dry_run(unsigned)
        outcome = dry_run.outcome
        if outcome is None or not outcome.is_commit:
            sys.exit(f"Dry run did not commit: {outcome}")
        print(f"Dry run successful. Estimated fee: {dry_run.estimated_fee}")

        # 5. Seal + send + watch the real transaction.
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        await wait("workspace chain", pending)

        # 6. Print the receipt — events list confirms all instructions
        #    fired atomically.
        receipt = await pending.get_receipt()
        print(f"\nEpoch: {receipt.epoch}")
        print(f"Fees charged: {receipt.fee_receipt.total_fees_charged}")
        print(f"Events ({len(receipt.events)}):")
        for ev in receipt.events:
            sid = ev.substate_id.opaque if ev.substate_id else "-"
            print(f"  {ev.topic} [{sid}] {ev.payload}")

        # 7. Balances after the chain. Sender lost the transfer + fees;
        #    recipient gained it (on top of its own faucet); extra account
        #    exists but holds nothing.
        sender_balance = await client.get_account_balance(sender_account, TARI_RESOURCE)
        recipient_balance = await client.get_account_balance(recipient_account, TARI_RESOURCE)
        print(f"\nSender TARI:    {sender_balance}")
        print(f"Recipient TARI: {recipient_balance}")
        print(f"Extra account created: {extra_account}")


if __name__ == "__main__":
    asyncio.run(main())
