"""``_types/_substate_json.py`` — externally-tagged ``SubstateValue`` parsing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ootle._types._bor_value import BinaryTag, iter_object_keys_hex
from ootle._types._indexer_json import parse_indexer_substate
from ootle._types._substate_json import parse_amount, parse_substate_value
from ootle._types.substate import (
    ComponentSubstateValue,
    ResourceSubstateValue,
    SubstateId,
    UnknownSubstateValue,
    VaultSubstateValue,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "substate_examples"


def _envelope(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _substate(name: str) -> dict[str, Any]:
    return _envelope(name)["substate"]


def test_parse_component_keeps_state_tree_and_header() -> None:
    value = parse_substate_value(_substate("component.json"))
    assert isinstance(value, ComponentSubstateValue)
    assert value.template_address == ("0" * 64)
    # state is the raw JSON-rendered tari_bor Value tree; the vault id is
    # discoverable through its @cbor-tagged nodes.
    found = list(iter_object_keys_hex(value.state, BinaryTag.VAULT_ID))
    assert found == ["c9cf5c5a8df5d023066b0901d425e8f55e7dbcbc01452671db2a01274631b8ff"]


def test_parse_vault_stealth_uses_revealed_amount() -> None:
    value = parse_substate_value(_substate("vault.json"))
    assert isinstance(value, VaultSubstateValue)
    assert value.container_kind == "stealth"
    assert value.resource_address.endswith("0101010101010101010101010101010101010101")
    assert int(value.balance) == 999_999_531


def test_parse_vault_fungible_uses_amount() -> None:
    payload: dict[str, Any] = {
        "Vault": {
            "resource_container": {
                "Fungible": {"address": "resource_aa", "amount": "42", "locked_amount": "0"}
            },
            "freeze_flags": 0,
        }
    }
    value = parse_substate_value(payload)
    assert isinstance(value, VaultSubstateValue)
    assert value.container_kind == "fungible"
    assert int(value.balance) == 42


def test_parse_vault_confidential_uses_revealed_amount() -> None:
    payload: dict[str, Any] = {
        "Vault": {
            "resource_container": {
                "Confidential": {
                    "address": "resource_cc",
                    "commitments": {},
                    "revealed_amount": "500",
                    "locked_commitments": {},
                    "locked_revealed_amount": "0",
                }
            },
            "freeze_flags": 0,
        }
    }
    value = parse_substate_value(payload)
    assert isinstance(value, VaultSubstateValue)
    assert value.container_kind == "confidential"
    assert int(value.balance) == 500


def test_parse_vault_non_fungible_has_zero_balance() -> None:
    payload: dict[str, Any] = {
        "Vault": {
            "resource_container": {
                "NonFungible": {"address": "resource_bb", "token_ids": [], "locked_token_ids": []}
            },
            "freeze_flags": 0,
        }
    }
    value = parse_substate_value(payload)
    assert isinstance(value, VaultSubstateValue)
    assert value.container_kind == "non_fungible"
    assert int(value.balance) == 0


def test_parse_vault_unknown_container_variant_raises() -> None:
    with pytest.raises(ValueError, match="unknown ResourceContainer variant"):
        parse_substate_value({"Vault": {"resource_container": {"Mystery": {"address": "r"}}}})


def test_parse_vault_non_object_container_raises() -> None:
    with pytest.raises(TypeError, match="`resource_container` must be an object"):
        parse_substate_value({"Vault": {"resource_container": "nope"}})


def test_parse_resource_optional_supply_and_metadata() -> None:
    value = parse_substate_value(_substate("resource.json"))
    assert isinstance(value, ResourceSubstateValue)
    assert value.total_supply is None
    assert value.divisibility == 6
    assert value.metadata == {"SYMBOL": "tTARI"}
    assert value.resource_type == "Stealth"


def test_parse_resource_with_supply_string() -> None:
    value = parse_substate_value({"Resource": {"total_supply": "21000000", "divisibility": 6}})
    assert isinstance(value, ResourceSubstateValue)
    assert value.total_supply is not None
    assert int(value.total_supply) == 21_000_000


def test_unknown_variant_round_trips_raw() -> None:
    payload = _substate("unknown.json")
    value = parse_substate_value(payload)
    assert isinstance(value, UnknownSubstateValue)
    assert value.discriminator == "NonFungible"
    assert value.raw == payload


def test_non_dict_variant_body_round_trips_as_unknown() -> None:
    value = parse_substate_value({"TransactionReceipt": "trx_abc"})
    assert isinstance(value, UnknownSubstateValue)
    assert value.discriminator == "TransactionReceipt"


def test_multi_key_payload_is_rejected() -> None:
    with pytest.raises(TypeError, match="externally-tagged SubstateValue"):
        parse_substate_value({"Component": {}, "Vault": {}})


def test_parse_amount_accepts_string_and_int() -> None:
    assert int(parse_amount("123")) == 123
    assert int(parse_amount(7)) == 7


@pytest.mark.parametrize("bad", [True, None, 1.5, []])
def test_parse_amount_rejects_other_types(bad: object) -> None:
    with pytest.raises(TypeError, match="Amount must be a string or integer"):
        parse_amount(bad)


def test_parse_indexer_substate_threads_id_and_version() -> None:
    sub = parse_indexer_substate(SubstateId("component_c9"), _envelope("component.json"))
    assert sub.id == SubstateId("component_c9")
    assert sub.version == 0
    assert isinstance(sub.value, ComponentSubstateValue)
