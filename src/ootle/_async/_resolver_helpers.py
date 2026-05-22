"""Internal helpers for :class:`AsyncTransactionInputResolver`.

Split out of ``_resolver.py`` to keep both files under the 200-line cap.
"""

from __future__ import annotations

import json
from typing import Any, cast

from ootle._types._bor_value import BinaryTag, iter_object_keys_hex
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.substate import (
    ComponentSubstateValue,
    Substate,
    SubstateId,
    SubstateRequirement,
    VaultSubstateValue,
)
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import IndexerClientError


def resolve_specific(
    sub_id: SubstateId,
    required: bool,
    cache: dict[SubstateId, Substate],
    missing: set[SubstateId],
    new_inputs: list[SubstateRequirement],
    to_fetch: list[SubstateId],
) -> bool:
    """Resolve a ``WantInput.SpecificSubstate``."""
    cached = cache.get(sub_id)
    if cached is not None:
        new_inputs.append(SubstateRequirement(id=sub_id, version=None))
        return True
    if sub_id in missing:
        if required:
            msg = f"required substate {sub_id.opaque} not found"
            raise IndexerClientError(msg, status=None, body="", url="")
        return True
    to_fetch.append(sub_id)
    return False


def resolve_stealth_commitment(
    commitment: bytes,
    resource: object,
    cache: dict[SubstateId, Substate],
    missing: set[SubstateId],
    new_inputs: list[SubstateRequirement],
    to_fetch: list[SubstateId],
) -> bool:
    """Resolve a ``WantInput.StealthCommitment`` to its on-chain UTXO input.

    Declares ``utxo_<resource>_<commitment>`` as an unversioned input: the engine
    DOWNs it while executing the ``StealthTransfer`` instruction and rejects the
    tx ("Substate not found") if a spent UTXO is not a declared input. Mirrors
    the Rust SDK's ``with_inputs(UtxoAddress…)``.
    """
    resource_hex = str(resource).removeprefix("resource_")
    sub_id = SubstateId(opaque=f"utxo_{resource_hex}_{commitment.hex()}")
    cached = cache.get(sub_id)
    if cached is not None:
        new_inputs.append(SubstateRequirement(id=sub_id, version=None))
        return True
    if sub_id in missing:
        msg = f"stealth input UTXO {sub_id.opaque} not found on indexer"
        raise IndexerClientError(msg, status=None, body="", url="")
    to_fetch.append(sub_id)
    return False


def resolve_vault(
    component: object,
    resource: object,
    required: bool,
    cache: dict[SubstateId, Substate],
    missing: set[SubstateId],
    new_inputs: list[SubstateRequirement],
    to_fetch: list[SubstateId],
) -> bool:
    """Resolve a ``WantInput.VaultForResource``."""
    component_id = SubstateId(opaque=str(component))
    cached = cache.get(component_id)
    if cached is None:
        if component_id in missing:
            if required:
                msg = f"required component substate {component_id.opaque} not found"
                raise IndexerClientError(msg, status=None, body="", url="")
            return True
        to_fetch.append(component_id)
        return False
    if not isinstance(cached.value, ComponentSubstateValue):
        return True
    vault_ids = extract_vault_ids(cached)
    have_all_vaults = True
    matched = False
    for vault_id in vault_ids:
        vault_cached = cache.get(vault_id)
        if vault_cached is None:
            if vault_id in missing:
                continue
            have_all_vaults = False
            to_fetch.append(vault_id)
            continue
        if isinstance(vault_cached.value, VaultSubstateValue) and str(
            vault_cached.value.resource_address
        ) == str(resource):
            new_inputs.append(SubstateRequirement(id=vault_id, version=None))
            if str(resource) != TARI_TOKEN:
                new_inputs.append(
                    SubstateRequirement(id=SubstateId(opaque=str(resource)), version=None)
                )
            matched = True
    if matched:
        return True
    if not have_all_vaults:
        return False
    if required:
        msg = f"required vault for resource {resource} on component {component} not found"
        raise IndexerClientError(msg, status=None, body="", url="")
    return True


def resolve_all_vaults(
    component: object,
    cache: dict[SubstateId, Substate],
    missing: set[SubstateId],
    new_inputs: list[SubstateRequirement],
    to_fetch: list[SubstateId],
) -> bool:
    """Resolve a ``WantInput.AllComponentVaults``."""
    component_id = SubstateId(opaque=str(component))
    cached = cache.get(component_id)
    if cached is None:
        if component_id in missing:
            msg = f"component substate {component_id.opaque} not found"
            raise IndexerClientError(msg, status=None, body="", url="")
        to_fetch.append(component_id)
        return False
    if not isinstance(cached.value, ComponentSubstateValue):
        return True
    vault_ids = extract_vault_ids(cached)
    all_cached = True
    for vault_id in vault_ids:
        vault_cached = cache.get(vault_id)
        if vault_cached is None:
            if vault_id in missing:
                msg = f"vault {vault_id.opaque} referenced by component but missing on indexer"
                raise IndexerClientError(msg, status=None, body="", url="")
            all_cached = False
            to_fetch.append(vault_id)
            continue
        if isinstance(vault_cached.value, VaultSubstateValue):
            new_inputs.append(SubstateRequirement(id=vault_id, version=None))
            res = str(vault_cached.value.resource_address)
            if res != TARI_TOKEN:
                new_inputs.append(SubstateRequirement(id=SubstateId(opaque=res), version=None))
    return all_cached


def extract_vault_ids(component: Substate) -> list[SubstateId]:
    """Walk a component's state tree and return every ``vault_<hex64>`` id, deduped."""
    value = component.value
    if not isinstance(value, ComponentSubstateValue):
        return []
    seen: set[str] = set()
    out: list[SubstateId] = []
    for key_hex in iter_object_keys_hex(value.state, BinaryTag.VAULT_ID):
        if key_hex not in seen:
            seen.add(key_hex)
            out.append(SubstateId(f"vault_{key_hex}"))
    return out


def fold_inputs(
    unsigned: UnsignedTransaction, new_inputs: list[SubstateRequirement]
) -> UnsignedTransaction:
    """Re-emit ``unsigned`` with ``new_inputs`` merged into its ``inputs`` list."""
    if not new_inputs:
        return unsigned
    payload: Any = json.loads(unsigned.json)
    if not isinstance(payload, dict):
        msg = "unsigned transaction JSON must be an object"
        raise IndexerClientError(msg, status=None, body="", url="")
    body = cast("dict[str, Any]", payload)
    existing = cast("list[dict[str, Any]]", body.setdefault("inputs", []))
    seen = {(e.get("substate_id"), e.get("version")) for e in existing}
    for req in new_inputs:
        key = (req.id.opaque, req.version)
        if key not in seen:
            existing.append({"substate_id": req.id.opaque, "version": req.version})
            seen.add(key)
    # Byte-stable serialisation matters for envelope hashing: keep the
    # compact separators and rely on CPython's insertion-order dict to
    # preserve the original key ordering. Do not change format flags
    # casually — any drift will alter the transaction hash.
    return UnsignedTransaction(json=json.dumps(body, separators=(",", ":")))
