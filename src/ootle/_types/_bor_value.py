"""Helpers for the JSON-rendered ``tari_bor::Value`` the indexer emits.

Tari's engine stores component state as a ``tari_bor::Value``. Over the JSON
wire (``tari_bor::value_serde``) values that map cleanly onto JSON are emitted
directly; the rest use a sentinel object keyed on ``"@cbor"``:

==========================  ===================================================
``Value`` variant           JSON shape
==========================  ===================================================
``Null``                    ``null``
``Bool`` / ``Float``        bool / number
``Integer`` (i64/u64 range) number
``Integer`` (wider)         ``{"@cbor": "int", "value": "<decimal>"}``
``Text``                    string
``Array``                   ``[<Value>, …]``
``Map`` (all keys ``Text``) ``{"<key>": <Value>, …}``
``Map`` (other keys)        ``{"@cbor": "map", "entries": [[<k>, <v>], …]}``
``Bytes``                   ``{"@cbor": "bytes", "hex": "<hex>"}``
``Tag``                     ``{"@cbor": "tag", "tag": <n>, "value": <Value>}``
==========================  ===================================================

On-chain object kinds (component addresses, vault ids, …) are carried as
``Tag`` nodes whose tag comes from :class:`BinaryTag`. This module walks the
tree and pulls those tagged byte payloads out — enough for the balance and
input-resolver layers to find vault ids without a BOR codec.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Iterator

# Tari ``ObjectKey``s — the body of address-like binary tags — are always
# 32 bytes; tagged byte strings of any other length are not object keys.
OBJECT_KEY_LEN = 32

_SENTINEL_KEY = "@cbor"
_SENTINEL_BYTES = "bytes"
_SENTINEL_MAP = "map"
_SENTINEL_TAG = "tag"
_TAG_ENTRY_PAIR = 2  # an ``entries`` element is a ``[key, value]`` pair


class BinaryTag(IntEnum):
    """Well-known CBOR tags from ``tari_template_lib_types::substates::binary_tag``."""

    COMPONENT_ADDRESS = 128
    METADATA = 129
    NON_FUNGIBLE_ADDRESS = 130
    RESOURCE_ADDRESS = 131
    VAULT_ID = 132
    BUCKET_ID = 133
    TRANSACTION_RECEIPT = 134
    PROOF_ID = 135
    CLAIMED_OUTPUT_TOMBSTONE_ADDRESS = 136
    TEMPLATE_ADDRESS = 137
    VALIDATOR_NODE_FEE_POOL = 138
    ALLOCATED_COMPONENT_ADDRESS = 139
    ALLOCATED_RESOURCE_ADDRESS = 140
    UTXO = 141


def _bytes_payload(node: Any) -> bytes | None:
    """Return the bytes of a ``{"@cbor": "bytes", "hex": …}`` node, else ``None``."""
    if not isinstance(node, dict):
        return None
    obj = cast("dict[str, Any]", node)
    if obj.get(_SENTINEL_KEY) != _SENTINEL_BYTES:
        return None
    raw = obj.get("hex")
    if not isinstance(raw, str):
        return None
    try:
        return bytes.fromhex(raw)
    except ValueError:
        return None


def iter_tagged_bytes(value: Any, tag: BinaryTag | int) -> Iterator[bytes]:
    """Yield the byte payload of every ``Tag(tag, Bytes(…))`` node in ``value``.

    Walks the JSON-rendered ``Value`` depth-first. ``Tag`` nodes whose inner
    value is not a byte string are skipped (but still recursed into). Plain
    (text-keyed) map keys are always strings and cannot carry tagged bytes, so
    only their values are walked.
    """
    want = int(tag)
    if isinstance(value, dict):
        node = cast("dict[str, Any]", value)
        sentinel = node.get(_SENTINEL_KEY)
        if isinstance(sentinel, str):
            yield from _iter_sentinel(node, sentinel, want)
            return
        for child in node.values():
            yield from iter_tagged_bytes(child, want)
    elif isinstance(value, list):
        for item in cast("list[Any]", value):
            yield from iter_tagged_bytes(item, want)


def _iter_sentinel(node: dict[str, Any], kind: str, want: int) -> Iterator[bytes]:
    if kind == _SENTINEL_TAG:
        inner = node.get("value")
        if node.get("tag") == want:
            payload = _bytes_payload(inner)
            if payload is not None:
                yield payload
        yield from iter_tagged_bytes(inner, want)
    elif kind == _SENTINEL_MAP:
        entries = node.get("entries")
        if isinstance(entries, list):
            for entry in cast("list[Any]", entries):
                if isinstance(entry, list) and len(cast("list[Any]", entry)) == _TAG_ENTRY_PAIR:
                    key, val = cast("list[Any]", entry)
                    yield from iter_tagged_bytes(key, want)
                    yield from iter_tagged_bytes(val, want)
    # ``bytes`` / ``int`` sentinels are leaves: a byte payload is only an
    # object key when it sits under a matching ``tag``, handled above.


def iter_object_keys_hex(value: Any, tag: BinaryTag | int) -> Iterator[str]:
    """Yield the lowercase hex of every 32-byte ``Tag(tag, Bytes(…))`` payload."""
    for payload in iter_tagged_bytes(value, tag):
        if len(payload) == OBJECT_KEY_LEN:
            yield payload.hex()
