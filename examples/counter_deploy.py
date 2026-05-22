"""Counter template deployment and interaction example.

Deploys a fresh Counter component from an on-chain template, calls
``increase()`` in the same transaction, then reads the component state
via the substate API. The sender is generated and funded on the fly;
only the template address is external.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    OOTLE_COUNTER_TEMPLATE=template_25519815d...7c2c \\
    uv run python -m examples.counter_deploy
"""

from __future__ import annotations

import asyncio
import os

from ootle import AsyncOotleClient, ComponentAddress, SubstateId, TemplateAddress, workspace

from ._common import faucet_and_wait, first_new_substate, indexer_url, new_wallet, wait

DEFAULT_TEMPLATE = "template_25519815d691922c323ffbbcaf840deb324b1179839255cfa6e509496e587c2c"


async def main() -> None:
    template = TemplateAddress(os.environ.get("OOTLE_COUNTER_TEMPLATE") or DEFAULT_TEMPLATE)

    sender, wallet = new_wallet()
    print(f"Sender: {sender.to_address().bech32m}")

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Network: {client.network.name}, epoch: {await client.get_epoch()}")

        # Step 1: faucet TARI to cover deployment fees.
        await faucet_and_wait(client)

        # Step 2: deploy Counter and call increase() atomically.
        #   call_function → new Counter on workspace["counter"]
        #   call_method   → increase() on workspace["counter"]
        unsigned = await (
            client.component()
            .call_function(template, "new")
            .put_last_instruction_output_on_workspace("counter")
            .call_method(workspace("counter"), "increase")
            .pay_fee(1000)
            .prepare()
        )
        print(f"\nDeploy tx JSON:\n{unsigned.json}\n")
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        await wait("deploy+increase", pending)

        receipt = await pending.get_receipt()
        print(f"\nEpoch: {receipt.epoch}")
        print(f"Fees charged: {receipt.fee_receipt.total_fees_charged}")
        if receipt.logs:
            print(f"Logs: {receipt.logs}")

        counter = first_new_substate(receipt.diff_summary, "component_")
        if counter is None:
            print("\ndiff_summary.upped:")
            for up in receipt.diff_summary.upped:
                print(f"  {up.substate_id.opaque} v{up.version}")
            print("\nCould not auto-extract component address — inspect the output above.")
            return
        counter_addr = ComponentAddress(counter.opaque)
        print(f"\nCounter component: {counter_addr}")

        # Step 3: read the counter state via the substate API.
        substate = await client.get_substate(SubstateId(opaque=str(counter_addr)))
        print(f"Counter substate version: {substate.version}")
        print(f"Counter state: {substate.value}")


if __name__ == "__main__":
    asyncio.run(main())
