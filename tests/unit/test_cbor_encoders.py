"""Coverage for ``ootle._types._cbor`` encoders."""

from __future__ import annotations

import cbor2
import pytest

from ootle._types._bor_value import BinaryTag
from ootle._types._cbor import (
    cbor_encode_amount,
    cbor_encode_bool,
    cbor_encode_bytes,
    cbor_encode_metadata,
    cbor_encode_resource_address,
    cbor_encode_str,
)

_RESOURCE_HEX = "00" * 32


def test_cbor_encode_str_roundtrips() -> None:
    blob = cbor_encode_str("hello")
    assert cbor2.loads(blob) == "hello"


def test_cbor_encode_bytes_roundtrips() -> None:
    blob = cbor_encode_bytes(b"\x00\xff\x01")
    assert cbor2.loads(blob) == b"\x00\xff\x01"


@pytest.mark.parametrize("value", [True, False])
def test_cbor_encode_bool_roundtrips(value: bool) -> None:
    blob = cbor_encode_bool(value)
    assert cbor2.loads(blob) is value


def test_cbor_encode_amount_zero() -> None:
    assert cbor2.loads(cbor_encode_amount(0)) == [0, 0]


def test_cbor_encode_amount_splits_u64() -> None:
    n = (1 << 64) + 7
    assert cbor2.loads(cbor_encode_amount(n)) == [7, 1]


def test_cbor_encode_amount_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        cbor_encode_amount(-1)


def test_cbor_encode_amount_rejects_overflow() -> None:
    with pytest.raises(ValueError, match="overflows u128"):
        cbor_encode_amount(1 << 128)


def test_cbor_encode_metadata_tags_with_129() -> None:
    blob = cbor_encode_metadata({"provider_name": "Acme"})
    decoded = cbor2.loads(blob)
    assert isinstance(decoded, cbor2.CBORTag)
    assert decoded.tag == 129
    assert decoded.value == {"provider_name": "Acme"}


def test_cbor_encode_metadata_sorts_keys() -> None:
    # Match Rust BTreeMap's ordering for byte-identical output.
    blob = cbor_encode_metadata({"b": "2", "a": "1"})
    decoded = cbor2.loads(blob)
    assert list(decoded.value.items()) == [("a", "1"), ("b", "2")]


def test_cbor_encode_metadata_empty() -> None:
    decoded = cbor2.loads(cbor_encode_metadata({}))
    assert decoded.tag == 129
    assert decoded.value == {}


@pytest.mark.parametrize("addr", [f"resource_{_RESOURCE_HEX}", _RESOURCE_HEX])
def test_cbor_encode_resource_address_accepts_prefixed_and_raw_hex(addr: str) -> None:
    decoded = cbor2.loads(cbor_encode_resource_address(addr))
    assert isinstance(decoded, cbor2.CBORTag)
    assert decoded.tag == int(BinaryTag.RESOURCE_ADDRESS)
    assert decoded.value == bytes.fromhex(_RESOURCE_HEX)
