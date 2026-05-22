"""``SubstateId``, ``SubstateRequirement``, ``SubstateValue`` matching."""

from __future__ import annotations

from ootle._types.address import ResourceAddress
from ootle._types.amount import Amount
from ootle._types.substate import (
    ComponentSubstateValue,
    ResourceSubstateValue,
    Substate,
    SubstateId,
    SubstateRequirement,
    SubstateValue,
    UnknownSubstateValue,
    VaultSubstateValue,
)


def _vault(resource: str = "res-1", balance: int = 0) -> VaultSubstateValue:
    return VaultSubstateValue(
        resource_address=ResourceAddress(resource),
        balance=Amount(balance),
        container_kind="fungible",
    )


def test_substate_requirement_equality_and_hash() -> None:
    a = SubstateRequirement(SubstateId("vault-1"), version=2)
    b = SubstateRequirement(SubstateId("vault-1"), version=2)
    c = SubstateRequirement(SubstateId("vault-1"), version=None)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert {a, b, c} == {a, c}


def test_substate_carries_value_and_version() -> None:
    sub = Substate(id=SubstateId("vault-1"), version=3, value=_vault(balance=100))
    assert sub.version == 3
    assert sub.id.opaque == "vault-1"


def _classify(value: SubstateValue) -> str:
    match value:
        case ComponentSubstateValue():
            return "component"
        case VaultSubstateValue():
            return "vault"
        case ResourceSubstateValue():
            return "resource"
        case UnknownSubstateValue():
            return "unknown"


def test_substate_value_match_branches_cover_every_kind() -> None:
    cases: list[SubstateValue] = [
        ComponentSubstateValue(state=[]),
        _vault(),
        ResourceSubstateValue(total_supply=Amount(42)),
        UnknownSubstateValue(discriminator="weird", raw={"a": "b"}),
    ]
    assert [_classify(c) for c in cases] == ["component", "vault", "resource", "unknown"]


def test_substate_value_kind_discriminator_is_set() -> None:
    assert ComponentSubstateValue().kind == "component"
    assert _vault().kind == "vault"
    assert ResourceSubstateValue(total_supply=None).kind == "resource"
    assert UnknownSubstateValue(discriminator="x", raw={}).kind == "unknown"


def test_resource_substate_value_defaults() -> None:
    r = ResourceSubstateValue(total_supply=None)
    assert r.divisibility == 0
    assert r.metadata == {}
    assert r.resource_type is None


def test_component_substate_value_defaults() -> None:
    c = ComponentSubstateValue()
    assert c.state == {}
    assert c.template_address is None
