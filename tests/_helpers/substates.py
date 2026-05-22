"""Builders for substate wire shapes and decoded ``Substate`` objects.

Mirrors what Tari's engine emits for component state, vaults and resource
containers, so tests can exercise the substate parsers and the
vault-discovery walk against realistic payloads without a live indexer.
"""

from __future__ import annotations

from typing import Any

from ootle._types._bor_value import BinaryTag
from ootle._types.address import ResourceAddress
from ootle._types.amount import Amount
from ootle._types.substate import (
    ComponentSubstateValue,
    Substate,
    SubstateId,
    VaultContainerKind,
    VaultSubstateValue,
)


def bor_tag(tag: BinaryTag, opaque: str) -> dict[str, Any]:
    """A ``{"@cbor": "tag", …}`` node wrapping a 32-byte object-key id."""
    return {
        "@cbor": "tag",
        "tag": int(tag),
        "value": {"@cbor": "bytes", "hex": opaque.split("_", 1)[-1]},
    }


def component_state(vaults: dict[str, str]) -> list[Any]:
    """A component ``state`` Value tree whose ``vaults`` map is ``{resource: vault}``.

    Mirrors the engine's account state: a BOR ``Array`` whose first element is
    the ``{resource: vault}`` map (non-text keys, so a ``@cbor`` map).
    """
    entries = [
        [bor_tag(BinaryTag.RESOURCE_ADDRESS, res), bor_tag(BinaryTag.VAULT_ID, vid)]
        for res, vid in vaults.items()
    ]
    return [{"@cbor": "map", "entries": entries}, {}]


def component_value(vaults: dict[str, str]) -> dict[str, Any]:
    """A ``SubstateValue`` body for an account component holding ``vaults``."""
    return {
        "Component": {
            "header": {"template_address": "00" * 32},
            "body": {"state": component_state(vaults)},
        }
    }


def fungible_vault_value(resource: str, amount: int) -> dict[str, Any]:
    """A ``SubstateValue`` body for a fungible vault."""
    return {
        "Vault": {
            "resource_container": {
                "Fungible": {"address": resource, "amount": str(amount), "locked_amount": "0"}
            },
            "freeze_flags": 0,
        }
    }


def envelope(value: dict[str, Any], *, version: int = 0) -> dict[str, Any]:
    """A ``GET /substates/{id}`` response body wrapping ``value``."""
    return {"version": version, "substate": value}


def component_substate(component_id: str, vaults: dict[str, str]) -> Substate:
    """A decoded :class:`Substate` for an account component holding ``vaults``."""
    return Substate(
        id=SubstateId(component_id),
        version=1,
        value=ComponentSubstateValue(state=component_state(vaults)),
    )


def vault_substate(
    vault_id: str, resource: str, *, balance: int = 0, kind: VaultContainerKind = "fungible"
) -> Substate:
    """A decoded :class:`Substate` for a vault holding ``balance`` of ``resource``."""
    return Substate(
        id=SubstateId(vault_id),
        version=1,
        value=VaultSubstateValue(
            resource_address=ResourceAddress(resource),
            balance=Amount(balance),
            container_kind=kind,
        ),
    )
