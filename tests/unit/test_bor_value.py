"""``_types/_bor_value.py`` — walking the JSON-rendered ``tari_bor::Value``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ootle._types._bor_value import BinaryTag, iter_object_keys_hex, iter_tagged_bytes

FIXTURES = Path(__file__).parent.parent / "fixtures" / "substate_examples"

# tag-132 (VaultId) payload embedded in the component fixture's state tree.
EXPECTED_VAULT_HEX = "c9cf5c5a8df5d023066b0901d425e8f55e7dbcbc01452671db2a01274631b8ff"


def _component_state() -> dict[str, Any]:
    envelope = json.loads((FIXTURES / "component.json").read_text(encoding="utf-8"))
    return envelope["substate"]["Component"]["body"]["state"]


def test_iter_object_keys_hex_finds_vault_id_in_component_state() -> None:
    found = list(iter_object_keys_hex(_component_state(), BinaryTag.VAULT_ID))
    assert found == [EXPECTED_VAULT_HEX]


def test_iter_object_keys_hex_finds_resource_address_tag() -> None:
    found = list(iter_object_keys_hex(_component_state(), BinaryTag.RESOURCE_ADDRESS))
    assert found == ["01" * 32]


def _tag(tag: int, hex_str: str) -> dict[str, Any]:
    return {"@cbor": "tag", "tag": tag, "value": {"@cbor": "bytes", "hex": hex_str}}


def test_iter_tagged_bytes_ignores_other_tags_and_non_byte_payloads() -> None:
    value = [
        _tag(132, "010203"),
        {"@cbor": "tag", "tag": 132, "value": "not-bytes"},
        _tag(999, "0909"),
        {"@cbor": "map", "entries": [["k", _tag(132, "0405")]]},
    ]
    assert [b.hex() for b in iter_tagged_bytes(value, BinaryTag.VAULT_ID)] == ["010203", "0405"]


def test_iter_object_keys_hex_filters_non_32_byte_payloads() -> None:
    assert list(iter_object_keys_hex(_tag(132, "010203"), BinaryTag.VAULT_ID)) == []


def test_iter_tagged_bytes_handles_scalars_and_null() -> None:
    assert list(iter_tagged_bytes(None, BinaryTag.VAULT_ID)) == []
    assert list(iter_tagged_bytes(5, BinaryTag.VAULT_ID)) == []
    assert list(iter_tagged_bytes("text", BinaryTag.VAULT_ID)) == []


def test_iter_tagged_bytes_recurses_into_tag_inner_value() -> None:
    # A tag wrapping a text-keyed map that itself contains a VaultId tag.
    value = {"@cbor": "tag", "tag": 129, "value": {"v": _tag(132, "07" * 32)}}
    assert [b.hex() for b in iter_tagged_bytes(value, BinaryTag.VAULT_ID)] == ["07" * 32]


def test_bytes_payload_accepts_full_byte_range() -> None:
    assert list(iter_tagged_bytes(_tag(132, "007fff"), BinaryTag.VAULT_ID)) == [b"\x00\x7f\xff"]


def test_bytes_payload_rejects_invalid_hex() -> None:
    assert list(iter_tagged_bytes(_tag(132, "zz"), BinaryTag.VAULT_ID)) == []
