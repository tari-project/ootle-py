"""Template publication example.

Funds a fresh account, dry-runs the publish to surface the real fee,
then publishes a compiled WASM template via ``IAccount.publish_template``
and confirms the resulting ``template_<hex>`` address by reading it back
through the substate API. The sender is generated and funded on the fly;
only the WASM blob is external.

There is no direct Rust counterpart in ``ootle-rs/examples/`` — the Rust
suite jumps straight to invoking already-published templates. Use this
example to obtain a ``TemplateAddress`` you can then feed into
``examples.counter_deploy`` or ``examples.template_invoke`` via their
respective env vars.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    OOTLE_TEMPLATE_WASM=/path/to/your_template.wasm \\
    uv run python -m examples.publish_template

Compile a template with::

    cargo build --target wasm32-unknown-unknown --release \\
        --manifest-path /path/to/your_template/Cargo.toml
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from ootle import AsyncOotleClient, SubstateId, TemplateAddress, TemplateBlob

from ._common import faucet_and_wait, first_new_substate, indexer_url, new_wallet, wait

# Publishing a WASM template is heavier than ordinary transactions — the engine
# stores the binary on-chain. Set a generous ceiling; the dry-run below surfaces
# the real cost before we commit to paying it.
PUBLISH_FEE = 500_000


def _read_wasm_blob() -> bytes:
    """Resolve and read the WASM blob to publish.

    Exits with a clear hint if ``OOTLE_TEMPLATE_WASM`` is unset or points
    to a missing file — template publishing requires a real WASM payload.
    """
    raw = os.environ.get("OOTLE_TEMPLATE_WASM") or ""
    if not raw:
        sys.exit(
            "OOTLE_TEMPLATE_WASM is required — set it to a compiled "
            "wasm32-unknown-unknown template binary, e.g.:\n"
            "  cargo build --target wasm32-unknown-unknown --release "
            "--manifest-path /path/to/your_template/Cargo.toml\n"
            "  OOTLE_TEMPLATE_WASM=/path/to/target/wasm32-unknown-unknown/"
            "release/your_template.wasm uv run python -m examples.publish_template"
        )
    path = Path(raw).expanduser()
    if not path.is_file():
        sys.exit(f"OOTLE_TEMPLATE_WASM points to a missing file: {path}")
    return path.read_bytes()


async def main() -> None:
    wasm_bytes = _read_wasm_blob()

    sender, wallet = new_wallet()
    print(f"Sender: {sender.to_address().bech32m}")
    print(f"WASM blob: {len(wasm_bytes)} bytes")

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Network: {client.network.name}, epoch: {await client.get_epoch()}")

        # Step 1: faucet TARI to cover the publish fee.
        await faucet_and_wait(client)

        # Step 2: build the publish-template transaction.
        unsigned = await (
            client.account()
            .pay_fee(PUBLISH_FEE)
            .publish_template(TemplateBlob(blob=wasm_bytes))
            .prepare()
        )

        # Step 3: dry-run to surface the real fee and any reject reason
        # before paying for the real send — publishing is expensive.
        dry_run = await client.send_dry_run(unsigned)
        outcome = dry_run.outcome
        if outcome is None or not outcome.is_commit:
            print(f"\nDry run did not commit: {outcome}")
            return
        print(f"\nDry run successful. Estimated fee: {dry_run.estimated_fee}")

        # Step 4: seal, send, watch finalisation.
        sealed = client.seal_transaction(unsigned)
        pending = await client.send_transaction(sealed)
        await wait("publish", pending)

        receipt = await pending.get_receipt()
        print(f"\nEpoch: {receipt.epoch}")
        print(f"Fees charged: {receipt.fee_receipt.total_fees_charged}")
        if receipt.logs:
            print(f"Logs: {receipt.logs}")

        found = first_new_substate(receipt.diff_summary, "template_")
        if found is None:
            print("\ndiff_summary.upped:")
            for up in receipt.diff_summary.upped:
                print(f"  {up.substate_id.opaque} v{up.version}")
            sys.exit("Could not auto-extract template address — inspect output above.")
        template_addr = TemplateAddress(found.opaque)
        print(f"\nPublished template: {template_addr}")

        # Step 5: confirm the template substate resolves on-chain.
        substate = await client.get_substate(SubstateId(opaque=str(template_addr)))
        print(f"Template substate version: {substate.version}")

        print("\nFeed it into the downstream examples with:")
        print(f"  OOTLE_COUNTER_TEMPLATE={template_addr}")


if __name__ == "__main__":
    asyncio.run(main())
