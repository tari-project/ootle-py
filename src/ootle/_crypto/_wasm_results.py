"""Result-unwrapping helpers shared by :class:`WasmCryptoProvider`.

The wasm-bindgen glue returns multi-value tuples; the shape varies by
return type:

- ``(ptr, len, err_ref, is_err)`` for owned byte/str returns.
- ``(box_ptr, err_ref, is_err)`` for boxed-struct returns.
- ``(is_some, value_u64, err_ref, is_err)`` for ``Result<Option<u64>>``.
- ``(err_ref, is_err)`` for ``Result<()>``.

The helpers below unpack those tuples, raise
:class:`~ootle.errors.CryptoBridgeError` on the failure path, and hand
back native Python values on success. They are sync — they bridge the
WASM ABI to Python without touching async at all.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ootle.errors import CryptoBridgeError

from ._bridge import Bridge, _abi

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass(frozen=True, slots=True)
class _BoxAccessor:
    """Reads fields out of a WASM box pointer. Scoped by :func:`open_box`."""

    bridge: Bridge
    ptr: int

    def read_bytes(self, getter: str) -> bytes:
        pl = self.bridge.exports[getter](self.bridge.store, self.ptr)
        return _abi.take_owned_bytes(self.bridge, pl[0], pl[1])

    def read_int(self, getter: str) -> int:
        return int(self.bridge.exports[getter](self.bridge.store, self.ptr))

    def read_optional_bytes(self, getter: str) -> bytes | None:
        pl = self.bridge.exports[getter](self.bridge.store, self.ptr)
        if pl[0] == 0:
            return None
        return _abi.take_owned_bytes(self.bridge, pl[0], pl[1])

    def read_optional_str(self, getter: str) -> str | None:
        """Read an ``Option<String>`` field — ``ptr == 0`` ⇒ ``None``, else UTF-8."""
        pl = self.bridge.exports[getter](self.bridge.store, self.ptr)
        if pl[0] == 0:
            return None
        return _abi.take_owned_str(self.bridge, pl[0], pl[1])


@contextmanager
def open_box(bridge: Bridge, box_ptr: int, freer: str) -> Generator[_BoxAccessor]:
    """Yield a :class:`_BoxAccessor`, freeing the WASM box on exit."""
    try:
        yield _BoxAccessor(bridge=bridge, ptr=box_ptr)
    finally:
        bridge.exports[freer](bridge.store, box_ptr, 0)


def take_bytes_result(bridge: Bridge, ret: Any, *, context: str) -> bytes:
    """Unwrap a ``(ptr, len, err_ref, is_err)`` tuple into ``bytes``."""
    if ret[3]:
        raise_from_externref(bridge, ret[2], context)
    return _abi.take_owned_bytes(bridge, ret[0], ret[1])


def take_str_result(bridge: Bridge, ret: Any, *, context: str) -> str:
    """Unwrap a ``(ptr, len, err_ref, is_err)`` tuple into ``str``."""
    if ret[3]:
        raise_from_externref(bridge, ret[2], context)
    return _abi.take_owned_str(bridge, ret[0], ret[1])


def take_box_result(bridge: Bridge, ret: Any, *, context: str) -> int:
    """Unwrap a ``(box_ptr, err_ref, is_err)`` tuple into ``int`` (box pointer)."""
    if ret[2]:
        raise_from_externref(bridge, ret[1], context)
    return int(ret[0])


def take_optional_u64_result(bridge: Bridge, ret: Any, *, context: str) -> int | None:
    """Unwrap a ``(is_some, value_u64, err_ref, is_err)`` tuple into ``int | None``."""
    if ret[3]:
        raise_from_externref(bridge, ret[2], context)
    if ret[0] == 0:
        return None
    return int(ret[1])


def take_unit_result(bridge: Bridge, ret: Any, *, context: str) -> None:
    """Unwrap a ``(err_ref, is_err)`` tuple; raise on error, else return ``None``."""
    if ret[1]:
        raise_from_externref(bridge, ret[0], context)


def raise_from_externref(bridge: Bridge, idx: int, context: str) -> None:
    """Take a JS-side error externref and raise a :class:`CryptoBridgeError`."""
    err = _abi.take_externref(bridge, idx)
    message = err if isinstance(err, str) else repr(err)
    raise CryptoBridgeError(message, context=context)
