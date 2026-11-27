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


def _encode_tagged_hex(addr: str, prefix: str, tag: BinaryTag) -> bytes:
    """Decode *addr* after stripping optional *prefix* and wrap in *tag*."""
    hex_str = addr.removeprefix(prefix)
    if not hex_str:
        msg = f"Missing hex payload in address: {addr!r}"
        raise ValueError(msg)
    return cbor2.dumps(cbor2.CBORTag(int(tag), bytes.fromhex(hex_str)))


def cbor_encode_component_address(addr: str) -> bytes:
    """CBOR-encode a ``ComponentAddress`` as ``BinaryTag::ComponentAddress(ObjectKey)``.

    Mirrors the Rust ``tari_bor::encode(&component_address)`` path — a CBOR tag
    128 wrapping the 32-byte ``ObjectKey`` bytes.
    """
    return _encode_tagged_hex(addr, "component_", BinaryTag.COMPONENT_ADDRESS)


def cbor_encode_resource_address(addr: str) -> bytes:
    """CBOR-encode a ``ResourceAddress`` as ``BinaryTag::ResourceAddress(ObjectKey)``.

    Mirrors the Rust ``tari_bor::encode(&resource_address)`` path used by the
    ``args!`` macro — a CBOR tag 131 wrapping the 32-byte ``ObjectKey`` bytes.
    """
    return _encode_tagged_hex(addr, "resource_", BinaryTag.RESOURCE_ADDRESS)


def cbor_encode_template_address(addr: str) -> bytes:
    """CBOR-encode a ``TemplateAddress`` as an untagged ``Hash32`` byte string.

    Mirrors ``ootle_sdk_core``'s ``encode_address`` path where
    ``SubstateId::Template`` lowers to ``TemplateAddress`` (``Hash32``), which
    encodes as raw CBOR bytes without a ``BinaryTag``.
    """
    hex_str = addr.removeprefix("template_")
    if not hex_str:
        msg = f"Missing hex payload in template address: {addr!r}"
        raise ValueError(msg)
    return cbor2.dumps(bytes.fromhex(hex_str))


def cbor_encode_address(addr: str) -> bytes:
    """CBOR-encode a prefixed ``ComponentAddress``, ``ResourceAddress``, or ``TemplateAddress``."""
    if addr.startswith("component_"):
        return cbor_encode_component_address(addr)
    if addr.startswith("resource_"):
        return cbor_encode_resource_address(addr)
    if addr.startswith("template_"):
        return cbor_encode_template_address(addr)
    msg = (
        f"Unrecognized address prefix in {addr!r}; expected 'component_', "
        "'resource_', or 'template_'"
    )
    raise ValueError(msg)


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
    """CBOR-encode an Amount as upstream's ``minicbor`` ``u128``.

    A plain unsigned integer up to ``u64::MAX``, a tag-2 positive bignum
    above it — which is how ``cbor2`` encodes a Python ``int``. The engine
    rejects any other shape for an ``Amount`` argument.
    """
    n = int(value)
    if n < 0:
        msg = f"Amount must be non-negative, got {n}"
        raise ValueError(msg)
    if (n >> 128) != 0:
        msg = f"Amount overflows u128: {n}"
        raise ValueError(msg)
    return cbor2.dumps(n)
