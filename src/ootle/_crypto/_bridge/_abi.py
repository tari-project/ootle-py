"""ABI helpers: linear-memory I/O, externref-table access, alloc/free.

These helpers are bound late: they take a :class:`Bridge` so they can read
``bridge.memory`` and ``bridge.exports`` dynamically. WASM memory grows
during execution, so the underlying buffer must be re-resolved on every
use rather than cached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import wasmtime

if TYPE_CHECKING:
    from . import Bridge


def read_bytes(bridge: Bridge, ptr: int, length: int) -> bytes:
    """Read ``length`` bytes starting at ``ptr`` from WASM linear memory."""
    return bytes(bridge.memory.read(bridge.store, ptr, ptr + length))


def write_bytes(bridge: Bridge, data: bytes | bytearray, ptr: int) -> None:
    bridge.memory.write(bridge.store, bytes(data), ptr)


def read_str(bridge: Bridge, ptr: int, length: int) -> str:
    return read_bytes(bridge, ptr, length).decode("utf-8")


def alloc_bytes(bridge: Bridge, data: bytes) -> tuple[int, int]:
    """``passArray8ToWasm0`` — copy ``data`` into a fresh WASM allocation."""
    length = len(data)
    ptr = _as_int(bridge.exports["__wbindgen_malloc"](bridge.store, length, 1))
    write_bytes(bridge, data, ptr)
    return ptr, length


def alloc_optional_bytes(bridge: Bridge, data: bytes | None) -> tuple[int, int]:
    """Encode ``Uint8Array | null`` — ``None`` → ``(0, 0)``."""
    if data is None:
        return 0, 0
    return alloc_bytes(bridge, data)


def alloc_str(bridge: Bridge, text: str) -> tuple[int, int]:
    """``passStringToWasm0`` — UTF-8 encode and copy into a fresh allocation."""
    encoded = text.encode("utf-8")
    return alloc_bytes(bridge, encoded)


def free(bridge: Bridge, ptr: int, length: int, align: int = 1) -> None:
    if ptr == 0 and length == 0:
        return
    bridge.exports["__wbindgen_free"](bridge.store, ptr, length, align)


def take_owned_bytes(bridge: Bridge, ptr: int, length: int) -> bytes:
    """Read a slice and immediately ``__wbindgen_free`` it.

    Mirrors the JS ``v1 = getArrayU8FromWasm0(...).slice(); free(...)`` pattern.
    """
    out = read_bytes(bridge, ptr, length)
    free(bridge, ptr, length)
    return out


def take_owned_str(bridge: Bridge, ptr: int, length: int) -> str:
    out = read_str(bridge, ptr, length)
    free(bridge, ptr, length)
    return out


def add_externref(bridge: Bridge, obj: Any) -> int:
    """Allocate a slot in ``__wbindgen_externrefs`` and store ``obj`` there."""
    table = _as_table(bridge.exports["__wbindgen_externrefs"])
    idx = _as_int(bridge.exports["__externref_table_alloc"](bridge.store))
    table.set(bridge.store, idx, obj)
    return idx


def take_externref(bridge: Bridge, idx: int) -> Any:
    """Read and deallocate the externref at ``idx``."""
    table = _as_table(bridge.exports["__wbindgen_externrefs"])
    value = table.get(bridge.store, idx)
    bridge.exports["__externref_table_dealloc"](bridge.store, idx)
    if isinstance(value, wasmtime.Val):
        return value.value
    return value


def _as_int(value: Any) -> int:
    if not isinstance(value, int):
        msg = f"expected i32, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _as_table(value: Any) -> wasmtime.Table:
    if not isinstance(value, wasmtime.Table):
        msg = f"expected wasmtime.Table, got {type(value).__name__}"
        raise TypeError(msg)
    return value
