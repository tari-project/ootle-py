"""``_async/_resolver_helpers`` — ``resolve_all_vaults``, ``extract_vault_ids``, ``fold_inputs``."""

from __future__ import annotations

import json

import pytest

from ootle._async._resolver_helpers import (
    extract_vault_ids,
    fold_inputs,
    resolve_all_vaults,
    resolve_vault,
)
from ootle._types._bor_value import BinaryTag
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.amount import Amount
from ootle._types.substate import (
    ComponentSubstateValue,
    ResourceSubstateValue,
    Substate,
    SubstateId,
    SubstateRequirement,
)
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import IndexerClientError
from tests._helpers.substates import bor_tag, component_substate, vault_substate

_OTHER_RES = "resource_" + ("aa" * 32)
_VAULT = "vault_" + ("bb" * 32)


def test_resolve_all_vaults_missing_component_raises() -> None:
    cache: dict[SubstateId, Substate] = {}
    missing: set[SubstateId] = {SubstateId("comp")}
    with pytest.raises(IndexerClientError, match="component substate"):
        resolve_all_vaults("comp", cache, missing, [], [])


def test_resolve_all_vaults_schedules_unknown_vault_fetch() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {TARI_TOKEN: _VAULT})
    }
    missing: set[SubstateId] = set()
    to_fetch: list[SubstateId] = []
    done = resolve_all_vaults("comp", cache, missing, [], to_fetch)
    assert done is False
    assert to_fetch == [SubstateId(_VAULT)]


def test_resolve_all_vaults_raises_when_referenced_vault_is_missing() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {TARI_TOKEN: _VAULT}),
    }
    missing: set[SubstateId] = {SubstateId(_VAULT)}
    with pytest.raises(IndexerClientError, match="referenced by component"):
        resolve_all_vaults("comp", cache, missing, [], [])


def test_resolve_all_vaults_adds_resource_for_non_tari() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {_OTHER_RES: _VAULT}),
        SubstateId(_VAULT): vault_substate(_VAULT, _OTHER_RES),
    }
    missing: set[SubstateId] = set()
    new_inputs: list[SubstateRequirement] = []
    done = resolve_all_vaults("comp", cache, missing, new_inputs, [])
    assert done is True
    assert {req.id.opaque for req in new_inputs} == {_VAULT, _OTHER_RES}
    # The called method may alter the resource, so it is declared a write.
    assert all(req.is_write for req in new_inputs)


def test_resolve_vault_declares_its_resource_a_read() -> None:
    """Deposits and withdrawals only read the resource (upstream ``VaultForResource``)."""
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): component_substate("comp", {_OTHER_RES: _VAULT}),
        SubstateId(_VAULT): vault_substate(_VAULT, _OTHER_RES),
    }
    new_inputs: list[SubstateRequirement] = []
    assert resolve_vault("comp", _OTHER_RES, True, cache, set(), new_inputs, []) is True
    assert new_inputs == [
        SubstateRequirement(SubstateId(_VAULT)),
        SubstateRequirement(SubstateId(_OTHER_RES), is_write=False),
    ]


def test_resolve_all_vaults_non_component_value_returns_done() -> None:
    cache: dict[SubstateId, Substate] = {
        SubstateId("comp"): Substate(
            id=SubstateId("comp"), version=1, value=ResourceSubstateValue(total_supply=Amount(0))
        )
    }
    missing: set[SubstateId] = set()
    assert resolve_all_vaults("comp", cache, missing, [], []) is True


def test_extract_vault_ids_non_component_value_returns_empty() -> None:
    component = Substate(
        id=SubstateId("comp"), version=1, value=ResourceSubstateValue(total_supply=Amount(0))
    )
    assert extract_vault_ids(component) == []


def test_extract_vault_ids_walks_nested_tree_and_dedupes() -> None:
    vault_node = bor_tag(BinaryTag.VAULT_ID, _VAULT)
    state = [
        vault_node,
        {"dup": vault_node},
        bor_tag(BinaryTag.RESOURCE_ADDRESS, _OTHER_RES),
    ]
    component = Substate(
        id=SubstateId("comp"), version=1, value=ComponentSubstateValue(state=state)
    )
    assert extract_vault_ids(component) == [SubstateId(_VAULT)]


def test_fold_inputs_no_op_for_empty_list() -> None:
    empty = UnsignedTransaction(json='{"inputs": []}')
    assert fold_inputs(empty, []) is empty


def test_fold_inputs_dedupes_against_existing_inputs() -> None:
    unsigned = UnsignedTransaction(json='{"inputs": [{"substate_id": "x", "version": null}]}')
    out = fold_inputs(unsigned, [SubstateRequirement(id=SubstateId("x"), version=None)])
    assert json.loads(out.json)["inputs"] == [
        {"substate_id": "x", "version": None, "is_write": True}
    ]


def test_fold_inputs_merges_declarations_of_one_substate() -> None:
    """Upstream rejects a substate declared twice: a read merges into a write, keeping its slot."""
    unsigned = UnsignedTransaction(
        json='{"inputs": [{"substate_id": "x", "version": 3, "is_write": false},'
        ' {"substate_id": "y", "version": null}]}'
    )
    out = fold_inputs(
        unsigned,
        [
            SubstateRequirement(id=SubstateId("x"), version=None),
            SubstateRequirement(id=SubstateId("y"), version=7, is_write=False),
        ],
    )
    assert json.loads(out.json)["inputs"] == [
        {"substate_id": "x", "version": 3, "is_write": True},
        {"substate_id": "y", "version": 7, "is_write": True},
    ]


def test_fold_inputs_rejects_malformed_existing_input() -> None:
    unsigned = UnsignedTransaction(json='{"inputs": [{"version": null}]}')
    with pytest.raises(IndexerClientError, match="malformed input declaration"):
        fold_inputs(unsigned, [SubstateRequirement(id=SubstateId("x"), version=None)])


def test_fold_inputs_rejects_non_object_payload() -> None:
    bad = UnsignedTransaction(json='["not", "an", "object"]')
    with pytest.raises(IndexerClientError, match="must be an object"):
        fold_inputs(bad, [SubstateRequirement(id=SubstateId("x"), version=None)])


def test_fold_inputs_uses_compact_byte_stable_serialisation() -> None:
    """Envelope hashing depends on byte-stable output; pin compact separators."""
    unsigned = UnsignedTransaction(json='{"fee_instructions":[],"instructions":[],"inputs":[]}')
    out = fold_inputs(unsigned, [SubstateRequirement(id=SubstateId("x"), version=None)])
    # No spaces after separators; original key order preserved.
    assert out.json == (
        '{"fee_instructions":[],"instructions":[],'
        '"inputs":[{"substate_id":"x","version":null,"is_write":true}]}'
    )
