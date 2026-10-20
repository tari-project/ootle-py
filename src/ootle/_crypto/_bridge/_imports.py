"""Wire the ``__wbg_*`` / ``__wbindgen_*`` host imports the WASM module declares.

The wasm-bindgen build exposes a minimal host surface: randomness
(``getRandomValues``), JS ``Error`` construction, the panic/throw hook
(``__wbindgen_throw``), externref-table initialisation, and the BigInt
intrinsics (``u64 -> externref`` cast, ``bigint_get_as_i64``, ``jsval_eq``)
that model JS ``BigInt`` values as Python ``int``. Each name
carries wasm-bindgen's mangling suffix — stable for a given vendored
blob, but regenerated on every upstream rebuild.

:func:`define_imports` keys handlers off the blob's actual
``module.imports`` and raises on any unmatched declared import, so a
stale dispatch table fails loudly at load rather than silently. Refresh
the names from a ``module.imports`` dump after re-vendoring (see
``scripts/update_wasm.py``).
"""

from __future__ import annotations

import secrets
import struct
from typing import TYPE_CHECKING

import wasmtime

from . import _abi

if TYPE_CHECKING:
    from collections.abc import Callable

    from . import Bridge

_U64_MASK = (1 << 64) - 1


def _build_handlers(bridge: Bridge) -> dict[str, Callable[..., object]]:
    def get_random_values(ptr: int, length_: int) -> None:
        """``globalThis.crypto.getRandomValues`` — fill ``length_`` bytes at ``ptr``."""
        _abi.write_bytes(bridge, secrets.token_bytes(length_), ptr)

    def throw_panic(ptr: int, length_: int) -> None:
        msg = _abi.take_owned_str(bridge, ptr, length_)
        bridge.panic_message = msg
        raise RuntimeError(f"WASM panic: {msg}")

    def make_error(ptr: int, length_: int) -> str:
        return _abi.read_str(bridge, ptr, length_)

    def externref_table_init() -> None:
        # The JS glue seeds undefined/null/true/false sentinels here, but the
        # exports we call return bool/Option as i32 (not externrefs) and surface
        # errors via dynamic __externref_table_alloc, so no seeding is required.
        return None

    def u64_to_externref(value: int) -> int:
        """``BigInt.asUintN(64, value)`` — wasmtime hands the u64 over as a signed i64."""
        return value & _U64_MASK

    def bigint_get_as_i64(ret_ptr: int, value: object) -> None:
        """Write ``(is_some: i32, _, value: i64)`` for a BigInt, else ``(0, _, 0)``."""
        is_bigint = isinstance(value, int) and not isinstance(value, bool)
        raw = value & _U64_MASK if is_bigint and isinstance(value, int) else 0
        _abi.write_bytes(bridge, struct.pack("<i", int(is_bigint)), ret_ptr)
        _abi.write_bytes(bridge, struct.pack("<Q", raw), ret_ptr + 8)

    def jsval_eq(a: object, b: object) -> int:
        """JS ``===``: no cross-type coercion, so ``True`` is not ``1n``."""
        return int(type(a) is type(b) and a == b)

    return {
        "__wbg_getRandomValues_47873ea553f6780e": get_random_values,
        "__wbg___wbindgen_throw_5d9e815e6fdf150f": throw_panic,
        "__wbg_Error_67e7344beaa85059": make_error,
        "__wbg___wbindgen_jsval_eq_9fdcd3c0a860dd3b": jsval_eq,
        "__wbg___wbindgen_bigint_get_as_i64_b482365c149396c8": bigint_get_as_i64,
        "__wbindgen_init_externref_table": externref_table_init,
        "__wbindgen_generic_0000000000000001": u64_to_externref,
    }


def define_imports(
    store: wasmtime.Store,
    module: wasmtime.Module,
    linker: wasmtime.Linker,
    bridge: Bridge,
) -> None:
    """Wire every host import the module declares onto the linker."""
    handlers = _build_handlers(bridge)
    for imp in module.imports:
        if not isinstance(imp.type, wasmtime.FuncType):
            continue
        name = imp.name or ""
        module_name = imp.module or ""
        handler = handlers.get(name)
        if handler is None:
            msg = f"missing host handler for WASM import {name!r}"
            raise RuntimeError(msg)
        linker.define(store, module_name, name, wasmtime.Func(store, imp.type, handler))
