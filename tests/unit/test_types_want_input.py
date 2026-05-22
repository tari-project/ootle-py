"""``WantInput`` member equality and set deduplication."""

from __future__ import annotations

from ootle._types.address import ComponentAddress, ResourceAddress
from ootle._types.substate import SubstateId
from ootle._types.want_input import WantInput


def test_vault_for_resource_equality_and_hash() -> None:
    a = WantInput.VaultForResource(
        component=ComponentAddress("c-1"),
        resource=ResourceAddress("r-1"),
    )
    b = WantInput.VaultForResource(
        component=ComponentAddress("c-1"),
        resource=ResourceAddress("r-1"),
    )
    assert a == b
    assert hash(a) == hash(b)


def test_specific_substate_default_required_is_true() -> None:
    s = WantInput.SpecificSubstate(id=SubstateId("vault-1"))
    assert s.required is True


def test_set_deduplicates_mixed_members() -> None:
    a = WantInput.VaultForResource(
        component=ComponentAddress("c"),
        resource=ResourceAddress("r"),
    )
    a_again = WantInput.VaultForResource(
        component=ComponentAddress("c"),
        resource=ResourceAddress("r"),
    )
    b = WantInput.SpecificSubstate(id=SubstateId("vault-1"))
    c = WantInput.AllComponentVaults(component=ComponentAddress("c-2"))
    items: set[
        WantInput.VaultForResource | WantInput.SpecificSubstate | WantInput.AllComponentVaults
    ] = {a, a_again, b, c}
    assert len(items) == 3
