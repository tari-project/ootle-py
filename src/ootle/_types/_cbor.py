"""CBOR encoding helpers used by the transaction-builder layer.

The Rust ``InstructionArg::Literal`` variant carries the body of a value
encoded with ``tari_bor::encode`` (CBOR over ``ciborium``); on the JSON
wire the bytes round-trip as a hex string. These helpers produce the
same CBOR shape for the v1 set of literal types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cbor2

from ootle._types._bor_value import BinaryTag

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ootle._types.amount import Amount


_U64_MASK = (1 << 64) - 1


def cbor_encode_resource_address(addr: str) -> bytes:
    """CBOR-encode a ``ResourceAddress`` as ``BinaryTag::ResourceAddress(ObjectKey)``.

    Mirrors the Rust ``tari_bor::encode(&resource_address)`` path used by the
    ``args!`` macro — a CBOR tag 131 wrapping the 32-byte ``ObjectKey`` bytes.
    """
    hash_bytes = bytes.fromhex(addr.removeprefix("resource_"))
    return cbor2.dumps(cbor2.CBORTag(int(BinaryTag.RESOURCE_ADDRESS), hash_bytes))


def cbor_encode_str(value: str) -> bytes:
    """CBOR-encode a string as a CBOR text string (Rust ``String``)."""
    return cbor2.dumps(value)


def cbor_encode_bytes(value: bytes) -> bytes:
    """CBOR-encode bytes as a CBOR byte string (Rust ``Vec<u8>``)."""
    return cbor2.dumps(value)


def cbor_encode_bool(value: bool) -> bytes:
    """CBOR-encode a bool as a CBOR boolean primitive."""
    return cbor2.dumps(value)


def cbor_encode_metadata(entries: Mapping[str, str]) -> bytes:
    """CBOR-encode a metadata mapping as ``Tag(129, Map<text, text>)``.

    Mirrors the ``Metadata = BorTag<BTreeMap<String, String>, 129>`` type
    used by templates (e.g. resource metadata, ``stable_coin::instantiate``).
    The inner map is emitted with keys sorted to match Rust's ``BTreeMap``
    ordering.
    """
    sorted_entries = dict(sorted(entries.items()))
    return cbor2.dumps(cbor2.CBORTag(int(BinaryTag.METADATA), sorted_entries))


def cbor_encode_amount(value: Amount | int) -> bytes:
    """CBOR-encode an Amount as the ``[lo, hi]`` u64 LE-digit pair.

    Mirrors the Rust ``Amount::serialize`` impl in the non-human-readable
    branch (the path used by ``tari_bor::encode``).
    """
    n = int(value)
    if n < 0:
        msg = f"Amount must be non-negative, got {n}"
        raise ValueError(msg)
    if (n >> 128) != 0:
        msg = f"Amount overflows u128: {n}"
        raise ValueError(msg)
    lo = n & _U64_MASK
    hi = (n >> 64) & _U64_MASK
    return cbor2.dumps([lo, hi])
