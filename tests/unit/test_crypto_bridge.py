"""Bridge micro-tests against the real WASM-backed Bridge.

These tests exercise the ABI helpers (string/bytes round-trip, externref
table mirror, panic capture) without yet touching the Protocol surface.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ootle._crypto._bridge import Bridge, _abi, load_default_bridge
from ootle._crypto._bridge._imports import (
    _build_handlers,  # pyright: ignore[reportPrivateUsage]  # internal access
)


@pytest.fixture(scope="module")
def bridge() -> Bridge:
    return load_default_bridge()


def test_load_default_bridge_is_singleton() -> None:
    a = load_default_bridge()
    b = load_default_bridge()
    assert a is b


def test_string_round_trip(bridge: Bridge) -> None:
    payload = "ootle bridge test 🦀"
    ptr, length = _abi.alloc_str(bridge, payload)
    try:
        assert _abi.read_str(bridge, ptr, length) == payload
    finally:
        _abi.free(bridge, ptr, length)


def test_bytes_round_trip(bridge: Bridge) -> None:
    payload = bytes(range(256))
    ptr, length = _abi.alloc_bytes(bridge, payload)
    try:
        assert _abi.read_bytes(bridge, ptr, length) == payload
    finally:
        _abi.free(bridge, ptr, length)


def test_alloc_optional_bytes_handles_none(bridge: Bridge) -> None:
    ptr, length = _abi.alloc_optional_bytes(bridge, None)
    assert (ptr, length) == (0, 0)


def test_take_owned_bytes_frees_memory(bridge: Bridge) -> None:
    payload = b"payload-to-be-freed"
    ptr, length = _abi.alloc_bytes(bridge, payload)
    out = _abi.take_owned_bytes(bridge, ptr, length)
    assert out == payload


def test_externref_table_round_trip(bridge: Bridge) -> None:
    payload = ["arbitrary", "python", "object"]
    idx = _abi.add_externref(bridge, payload)
    assert _abi.take_externref(bridge, idx) is payload


def test_panic_path_via_invalid_address_surface(bridge: Bridge) -> None:
    """Calling parseOotleAddress with junk returns a host-Error externref."""
    ptr, length = _abi.alloc_str(bridge, "definitely-not-a-bech32m-address")
    ret = cast("list[Any]", bridge.exports["parseOotleAddress"](bridge.store, ptr, length))
    assert ret[2] == 1, "expected the is_error flag set"
    err = _abi.take_externref(bridge, int(ret[1]))
    assert isinstance(err, str)
    assert "Bech32" in err or "address" in err.lower()


def test_bigint_import_handlers(bridge: Bridge) -> None:
    handlers = _build_handlers(bridge)
    cast_u64 = handlers["__wbindgen_generic_0000000000000001"]
    get_as_i64 = handlers["__wbg___wbindgen_bigint_get_as_i64_b482365c149396c8"]
    jsval_eq = handlers["__wbg___wbindgen_jsval_eq_9fdcd3c0a860dd3b"]

    assert cast_u64(-1) == 2**64 - 1
    assert jsval_eq(5, 5) == 1
    assert jsval_eq(True, 1) == 0

    ptr, length = _abi.alloc_bytes(bridge, bytes(16))
    try:
        get_as_i64(ptr, 2**64 - 1)
        assert _abi.read_bytes(bridge, ptr, 4) == (1).to_bytes(4, "little")
        assert _abi.read_bytes(bridge, ptr + 8, 8) == b"\xff" * 8
        get_as_i64(ptr, "not a bigint")
        assert _abi.read_bytes(bridge, ptr, 4) == bytes(4)
        assert _abi.read_bytes(bridge, ptr + 8, 8) == bytes(8)
    finally:
        _abi.free(bridge, ptr, length)
