"""``_async/_resolver_helpers`` — ``resolve_specific`` and ``resolve_vault``.

The ``resolve_all_vaults`` / ``extract_vault_ids`` / ``fold_inputs`` branches
live in ``test_resolver_helpers_extra``. The I/O-driven path is covered by
``tests/_async/test_resolver``.
"""

from __future__ import annotations

import pytest

from ootle._async._resolver_helpers import resolve_specific, resolve_vault
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.amount import Amount
from ootle._types.substate import (
    ResourceSubstateValue,
    Substate,
    SubstateId,
    SubstateRequirement,
)
from ootle.errors import IndexerClientError
from tests._helpers.substates import component_substate, vault_substate

_OTHER_RES = "resource_" + ("aa" * 32)
_VAULT = "vault_" + ("bb" * 32)


def test_resolve_specific_required_unknown_schedules_fetch() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = set()
    new_inputs: list[SubstateRequirement] = []
    to_fetch: list[SubstateId] = []
    done = resolve_specific(SubstateId("component_x"), True, cache, missing, new_inputs, to_fetch)
    assert done is False
    assert new_inputs == []
    assert to_fetch == [SubstateId("component_x")]


def test_resolve_specific_required_missing_raises() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = {SubstateId("component_x")}
    with pytest.raises(IndexerClientError, match="required substate"):
        resolve_specific(SubstateId("component_x"), True, cache, missing, [], [])


def test_resolve_specific_optional_unknown_schedules_fetch() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = set()
    to_fetch: list[SubstateId] = []
    done = resolve_specific(SubstateId("component_x"), False, cache, missing, [], to_fetch)
    assert done is False
    assert to_fetch == [SubstateId("component_x")]


def test_resolve_specific_optional_cached_none_skipped() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = {SubstateId("c")}
    new_inputs: list[SubstateRequirement] = []
    done = resolve_specific(SubstateId("c"), False, cache, missing, new_inputs, [])
    assert done is True
    assert new_inputs == []


def test_resolve_vault_required_missing_component_raises() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = {SubstateId("comp")}
    with pytest.raises(IndexerClientError, match="required component substate"):
        resolve_vault("comp", _OTHER_RES, True, cache, missing, [], [])


def test_resolve_vault_optional_missing_component_returns_done() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = {SubstateId("comp")}
    new_inputs: list[SubstateRequirement] = []
    done = resolve_vault("comp", _OTHER_RES, False, cache, missing, new_inputs, [])
    assert done is True
    assert new_inputs == []


def test_resolve_vault_match_adds_resource_for_non_tari() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {_OTHER_RES: _VAULT}),
        SubstateId(_VAULT): vault_substate(_VAULT, _OTHER_RES),
    }
    missing: set[SubstateId] = set()
    new_inputs: list[SubstateRequirement] = []
    done = resolve_vault("comp", _OTHER_RES, True, cache, missing, new_inputs, [])
    assert done is True
    assert {req.id.opaque for req in new_inputs} == {_VAULT, _OTHER_RES}


def test_resolve_vault_match_for_tari_does_not_add_resource() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {TARI_TOKEN: _VAULT}),
        SubstateId(_VAULT): vault_substate(_VAULT, TARI_TOKEN),
    }
    missing: set[SubstateId] = set()
    new_inputs: list[SubstateRequirement] = []
    done = resolve_vault("comp", TARI_TOKEN, True, cache, missing, new_inputs, [])
    assert done is True
    assert {req.id.opaque for req in new_inputs} == {_VAULT}


def test_resolve_vault_required_no_match_after_full_cache_raises() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {TARI_TOKEN: _VAULT}),
        SubstateId(_VAULT): vault_substate(_VAULT, TARI_TOKEN),
    }
    missing: set[SubstateId] = set()
    with pytest.raises(IndexerClientError, match="required vault"):
        resolve_vault("comp", _OTHER_RES, True, cache, missing, [], [])


def test_resolve_vault_two_pass_schedules_vault_fetch() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {TARI_TOKEN: _VAULT})
    }
    missing: set[SubstateId] = set()
    to_fetch: list[SubstateId] = []
    done = resolve_vault("comp", TARI_TOKEN, False, cache, missing, [], to_fetch)
    assert done is False
    assert to_fetch == [SubstateId(_VAULT)]


def test_resolve_vault_non_component_value_returns_done() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): Substate(
            id=SubstateId("comp"), version=1, value=ResourceSubstateValue(total_supply=Amount(0))
        )
    }
    missing: set[SubstateId] = set()
    assert resolve_vault("comp", TARI_TOKEN, False, cache, missing, [], []) is True
