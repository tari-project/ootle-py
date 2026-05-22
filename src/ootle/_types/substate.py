"""``SubstateId``, ``Substate``, ``SubstateRequirement`` and the
discriminated ``SubstateValue`` union.

The variants mirror the externally-tagged ``SubstateValue`` enum the
indexer serialises (``{"Component": …}``, ``{"Vault": …}``,
``{"Resource": …}``, …). Only the shapes the v1 surface consumes are
spelled out; richer variants round-trip through
:class:`UnknownSubstateValue` until a consumer needs them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ootle._types.address import ResourceAddress, TemplateAddress
    from ootle._types.amount import Amount


VaultContainerKind = Literal["fungible", "non_fungible", "confidential", "stealth"]
"""Which ``ResourceContainer`` variant backs a vault."""


@dataclass(frozen=True, slots=True)
class SubstateId:
    """An indexer-defined substate identifier."""

    opaque: str


@dataclass(frozen=True, slots=True)
class SubstateRequirement:
    """A reference to a substate, optionally pinned to a version."""

    id: SubstateId
    version: int | None = None


@dataclass(frozen=True, slots=True)
class ComponentSubstateValue:
    """A component substate — template state plus a slice of its header.

    ``state`` is the JSON-rendered ``tari_bor::Value`` tree the indexer
    emits — natural JSON for text-keyed maps/arrays plus ``"@cbor"``
    sentinels for bytes/tags/non-text maps; :mod:`ootle._types._bor_value`
    walks it. It can be a list or a dict, so it is typed opaquely.
    """

    state: object = field(default_factory=dict[str, Any])
    template_address: TemplateAddress | None = None
    kind: Literal["component"] = "component"


@dataclass(frozen=True, slots=True)
class VaultSubstateValue:
    """A vault substate — holds a balance of one resource.

    ``balance`` is the vault's scalar balance: the ``amount`` of a
    fungible container, the ``revealed_amount`` of a confidential or
    stealth one, and ``0`` for a non-fungible container (which has no
    scalar balance).
    """

    resource_address: ResourceAddress
    balance: Amount
    container_kind: VaultContainerKind
    kind: Literal["vault"] = "vault"


@dataclass(frozen=True, slots=True)
class ResourceSubstateValue:
    """A resource substate — its supply, divisibility and metadata.

    ``total_supply`` is ``None`` when the resource does not track supply.
    """

    total_supply: Amount | None
    divisibility: int = 0
    metadata: dict[str, str] = field(default_factory=dict[str, str])
    resource_type: str | None = None
    kind: Literal["resource"] = "resource"


@dataclass(frozen=True, slots=True)
class UnknownSubstateValue:
    """Catch-all for substate variants the v1 client doesn't decode yet.

    Carries the raw externally-tagged JSON payload so callers can inspect
    it; ``discriminator`` preserves the upstream enum-variant name.
    """

    discriminator: str
    raw: dict[str, Any]
    kind: Literal["unknown"] = "unknown"


SubstateValue = (
    ComponentSubstateValue | VaultSubstateValue | ResourceSubstateValue | UnknownSubstateValue
)


@dataclass(frozen=True, slots=True)
class Substate:
    """A versioned substate with its decoded value."""

    id: SubstateId
    version: int
    value: SubstateValue
