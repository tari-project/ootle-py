"""Stable-coin template invocation example (untyped ``IComponent`` path).

The sender is generated and funded on the fly; the template/component to
invoke is external. Two modes:

* ``OOTLE_STABLECOIN_TEMPLATE=template_<hex>`` — instantiate a fresh
  component, extract its address from the receipt, then invoke methods.
* ``OOTLE_STABLECOIN_COMPONENT=component_<hex>`` — skip instantiation
  and call methods on an existing component (cheap re-runs).

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    OOTLE_STABLECOIN_TEMPLATE=template_<hex> \\
    uv run python -m examples.template_invoke
"""

from __future__ import annotations

import asyncio
import os
import sys

from ootle import (
    AsyncOotleClient,
    ComponentAddress,
    TemplateAddress,
    args,
    metadata,
    workspace,
)

from ._common import faucet_and_wait, first_new_substate, indexer_url, new_wallet, wait

# Matches the Rust upstream's ``RistrettoPublicKeyBytes::default()`` — a
# 32-byte zero key. Replace with a real view key when wiring this into a
# flow that exercises stealth / view-only auth.
DEFAULT_VIEW_KEY = bytes(32)

INITIAL_SUPPLY = 1_000_000_000
COIN_SYMBOL = "OPY"
COIN_METADATA = {"provider_name": "OotlePythonExample"}
ENABLE_WRAPPED_TOKEN = False


def _read_env() -> tuple[str | None, str | None]:
    template = os.environ.get("OOTLE_STABLECOIN_TEMPLATE") or None
    component = os.environ.get("OOTLE_STABLECOIN_COMPONENT") or None
    if template and not template.startswith("template_"):
        sys.exit(f"OOTLE_STABLECOIN_TEMPLATE must start with 'template_' (got {template!r}).")
    if component and not component.startswith("component_"):
        hint = (
            " — looks like a template address; set OOTLE_STABLECOIN_TEMPLATE instead"
            if component.startswith("template_")
            else ""
        )
        sys.exit(
            f"OOTLE_STABLECOIN_COMPONENT must start with 'component_' (got {component!r}){hint}."
        )
    return template, component


async def _instantiate(
    client: AsyncOotleClient,
    template: TemplateAddress,
    sender_component: ComponentAddress,
) -> ComponentAddress:
    print(f"\nInstantiating stable coin from {template} ...")
    # ``instantiate`` returns the admin-badge Bucket; deposit it into the
    # sender's account in the same tx, otherwise the engine rejects with
    # "dangling buckets remain after transaction execution".
    unsigned = await (
        client.component()
        .call_function(
            template,
            "instantiate",
            args=args(
                INITIAL_SUPPLY,
                COIN_SYMBOL,
                metadata(COIN_METADATA),
                DEFAULT_VIEW_KEY,
                ENABLE_WRAPPED_TOKEN,
            ),
        )
        .put_last_instruction_output_on_workspace("admin_badge")
        .call_method(sender_component, "deposit", args=[workspace("admin_badge")])
        .pay_fee(5000)
        .prepare()
    )
    sealed = client.seal_transaction(unsigned)
    pending = await client.send_transaction(sealed)
    await wait("instantiate", pending)

    receipt = await pending.get_receipt()
    found = first_new_substate(receipt.diff_summary, "component_", exclude={str(sender_component)})
    if found is None:
        print("\ndiff_summary.upped:")
        for up in receipt.diff_summary.upped:
            print(f"  {up.substate_id.opaque} v{up.version}")
        print("\nReceipt events:")
        for e in receipt.events:
            print(f"  {e.topic} substate_id={e.substate_id}")
        sys.exit("Could not extract new component address — inspect output above.")
    component = ComponentAddress(found.opaque)
    print(f"  New stable-coin component: {component}")
    return component


async def _call_total_supply(client: AsyncOotleClient, component: ComponentAddress) -> None:
    """Invoke the AllowAll ``total_supply()`` method on the stable-coin component.

    Admin-gated methods (``increase_supply``, ``decrease_supply``, …) require
    the caller to present the admin-badge resource via a ``create_proof`` flow.
    That primitive is not exposed in v1 of the Python client — calling them
    here would silently get ``AcceptFeeRejectRest`` with ``Access Denied``.
    """
    print(f"\nCalling total_supply() on {component} ...")
    unsigned = await (
        client.component().call_method(component, "total_supply").pay_fee(2000).prepare()
    )
    sealed = client.seal_transaction(unsigned)
    pending = await client.send_transaction(sealed)
    await wait("total_supply", pending)


async def main() -> None:
    template_hex, component_hex = _read_env()
    if not template_hex and not component_hex:
        sys.exit(
            "Set OOTLE_STABLECOIN_TEMPLATE=template_<hex> to instantiate a fresh "
            "stable coin, or OOTLE_STABLECOIN_COMPONENT=component_<hex> to invoke "
            "an existing one."
        )

    sender, wallet = new_wallet()
    print(f"Sender address: {sender.to_address().bech32m}")
    sender_component = sender.to_address().to_component_address()

    async with AsyncOotleClient.connect(indexer_url(), wallet=wallet) as client:
        print(f"Network: {client.network.name}, epoch: {await client.get_epoch()}")
        await faucet_and_wait(client)

        if component_hex:
            component = ComponentAddress(component_hex)
            print(f"\nUsing existing stable-coin component: {component}")
        elif template_hex:
            component = await _instantiate(client, TemplateAddress(template_hex), sender_component)
        else:  # unreachable — guarded above
            sys.exit("internal error: neither template nor component resolved")

        await _call_total_supply(client, component)
        print("\nAll operations completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
