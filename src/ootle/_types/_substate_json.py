"""Parser for the indexer's externally-tagged ``SubstateValue`` enum.

Split out of :mod:`ootle._types._json` so each file stays under the
200-line cap. The shapes here mirror
``tari_ootle_common_types::engine_types`` exactly — there is no ``kind``
discriminator on the wire; ``SubstateValue`` is an externally-tagged
enum (``{"Component": …}``, ``{"Vault": …}``, ``{"Resource": …}``, …)
and ``Amount`` is a JSON string (or, tolerated, a number).
"""

from __future__ import annotations

from typing import Any, cast

from ootle._types._json_helpers import require_str
from ootle._types.address import ResourceAddress, TemplateAddress
from ootle._types.amount import Amount
from ootle._types.substate import (
    ComponentSubstateValue,
    ResourceSubstateValue,
    SubstateValue,
    UnknownSubstateValue,
    VaultContainerKind,
    VaultSubstateValue,
)

_CONTAINER_KINDS: dict[str, VaultContainerKind] = {
    "Fungible": "fungible",
    "NonFungible": "non_fungible",
    "Confidential": "confidential",
    "Stealth": "stealth",
}


def parse_substate_value(payload: dict[str, Any]) -> SubstateValue:
    """Decode an externally-tagged ``SubstateValue`` into a typed value.

    Variants the v1 client doesn't model round-trip through
    :class:`UnknownSubstateValue` so the caller can still inspect them.
    """
    variant, body = _unwrap_tagged(payload, "SubstateValue")
    if not isinstance(body, dict):
        return UnknownSubstateValue(discriminator=variant, raw=dict(payload))
    body_dict = cast("dict[str, Any]", body)
    if variant == "Component":
        return _parse_component(body_dict)
    if variant == "Vault":
        return _parse_vault(body_dict)
    if variant == "Resource":
        return _parse_resource(body_dict)
    return UnknownSubstateValue(discriminator=variant, raw=dict(payload))


def parse_amount(value: Any) -> Amount:
    """Parse a Tari ``Amount`` — a decimal JSON string, or a bare integer."""
    if isinstance(value, bool):
        msg = "Amount must be a string or integer, got bool"
        raise TypeError(msg)
    if isinstance(value, int):
        return Amount(value)
    if isinstance(value, str):
        return Amount(int(value))
    msg = f"Amount must be a string or integer, got {type(value).__name__}"
    raise TypeError(msg)


def _parse_component(body: dict[str, Any]) -> ComponentSubstateValue:
    template: TemplateAddress | None = None
    header = body.get("header")
    if isinstance(header, dict):
        raw = cast("dict[str, Any]", header).get("template_address")
        if isinstance(raw, str):
            template = TemplateAddress(raw)
    state: object = {}
    component_body = body.get("body")
    if isinstance(component_body, dict):
        state = cast("dict[str, Any]", component_body).get("state", {})
    return ComponentSubstateValue(state=state, template_address=template)


def _parse_vault(body: dict[str, Any]) -> VaultSubstateValue:
    container = body.get("resource_container")
    if not isinstance(container, dict):
        msg = "vault `resource_container` must be an object"
        raise TypeError(msg)
    variant, fields = _unwrap_tagged(cast("dict[str, Any]", container), "ResourceContainer")
    container_kind = _CONTAINER_KINDS.get(variant)
    if container_kind is None:
        msg = f"unknown ResourceContainer variant: {variant!r}"
        raise ValueError(msg)
    if not isinstance(fields, dict):
        msg = "ResourceContainer body must be an object"
        raise TypeError(msg)
    fd = cast("dict[str, Any]", fields)
    return VaultSubstateValue(
        resource_address=ResourceAddress(require_str(fd, "address")),
        balance=_container_balance(variant, fd),
        container_kind=container_kind,
    )


def _container_balance(variant: str, fields: dict[str, Any]) -> Amount:
    if variant == "Fungible":
        return parse_amount(fields["amount"])
    if variant in ("Confidential", "Stealth"):
        return parse_amount(fields["revealed_amount"])
    return Amount(0)  # NonFungible — no scalar balance


def _parse_resource(body: dict[str, Any]) -> ResourceSubstateValue:
    raw_supply = body.get("total_supply")
    total_supply = None if raw_supply is None else parse_amount(raw_supply)
    raw_div = body.get("divisibility")
    divisibility = raw_div if isinstance(raw_div, int) and not isinstance(raw_div, bool) else 0
    raw_type = body.get("resource_type")
    return ResourceSubstateValue(
        total_supply=total_supply,
        divisibility=divisibility,
        metadata=_str_dict(body.get("metadata")),
        resource_type=raw_type if isinstance(raw_type, str) else None,
    )


def _str_dict(value: Any) -> dict[str, str]:
    """Return a ``str → str`` view of ``value`` when it is a dict, else ``{}``."""
    if not isinstance(value, dict):
        return {}
    items = cast("dict[Any, Any]", value).items()
    return {k: v for k, v in items if isinstance(k, str) and isinstance(v, str)}


def _unwrap_tagged(payload: dict[str, Any], what: str) -> tuple[str, Any]:
    """Return ``(variant, body)`` for a single-key externally-tagged enum object."""
    if len(payload) != 1:
        msg = f"expected an externally-tagged {what}, got {len(payload)} key(s)"
        raise TypeError(msg)
    ((variant, body),) = payload.items()
    return variant, body
