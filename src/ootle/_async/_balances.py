"""Account balance helpers — built on the read-only transport.

Mirrors the algorithm in ``ootle-rs/src/provider/balance.rs``: given an
account ``ComponentAddress``, fetch its component substate, walk its
state for vault-id references, fetch the vaults in one batched call, and
aggregate ``Amount`` by ``ResourceAddress``.

The Rust client extracts vault ids via ``IndexedWellKnownTypes`` (a typed
BOR-walking visitor). The vendored WASM blob does not export that helper,
so we walk the JSON-rendered ciborium ``Value`` the indexer hands us and
pick up ``Tag(VaultId, Bytes(..32..))`` nodes — the same information the
BOR visitor surfaces (see :mod:`ootle._types._bor_value`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle._types._bor_value import BinaryTag, iter_object_keys_hex
from ootle._types.amount import Amount
from ootle._types.substate import (
    ComponentSubstateValue,
    Substate,
    SubstateId,
    VaultSubstateValue,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ootle._types.address import ComponentAddress, ResourceAddress

    from ._transport import AsyncIndexerTransport


async def get_account_balance(
    transport: AsyncIndexerTransport,
    account: ComponentAddress,
    resource: ResourceAddress,
) -> Amount:
    """Return the balance of ``resource`` held by ``account``.

    Returns ``Amount(0)`` if the account holds no vault for ``resource``.
    """
    balances = await get_account_balances(transport, account)
    return balances.get(resource, Amount(0))


async def get_account_balances(
    transport: AsyncIndexerTransport,
    account: ComponentAddress,
) -> dict[ResourceAddress, Amount]:
    """Return ``{resource_address: balance}`` for every vault on ``account``.

    Returns ``{}`` if the component does not exist or holds no vaults.
    """
    component = await transport.fetch_substate(SubstateId(opaque=account))
    if component is None:
        return {}
    vault_ids = list(_extract_vault_ids(component))
    if not vault_ids:
        return {}
    vaults = await transport.fetch_substates(vault_ids)
    balances: dict[ResourceAddress, Amount] = {}
    for substate in vaults.values():
        value = substate.value
        if isinstance(value, VaultSubstateValue):
            balances[value.resource_address] = value.balance
    return balances


def _extract_vault_ids(component: Substate) -> Iterable[SubstateId]:
    """Walk a component's state tree and yield its ``vault_<hex64>`` ids.

    Mirrors :class:`tari_engine_types::IndexedWellKnownTypes` — unique
    :class:`SubstateId`\\ s in stable insertion order.
    """
    value = component.value
    if not isinstance(value, ComponentSubstateValue):
        return
    seen: set[str] = set()
    for key_hex in iter_object_keys_hex(value.state, BinaryTag.VAULT_ID):
        if key_hex not in seen:
            seen.add(key_hex)
            yield SubstateId(f"vault_{key_hex}")
