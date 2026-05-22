"""Wire the four ``__wbg_*`` host imports the WASM module declares.

The wasm-bindgen build exposes a minimal host surface: randomness
(``getRandomValues``), JS ``Error`` construction, the panic/throw hook
(``__wbindgen_throw``), and externref-table initialisation. Each name
carries wasm-bindgen's mangling suffix — stable for a given vendored
blob, but regenerated on every upstream rebuild.

:func:`define_imports` keys handlers off the blob's actual
``module.imports`` and raises on any unmatched declared import, so a
stale dispatch table fails loudly at load rather than silently. Refresh
the four names from a ``module.imports`` dump after re-vendoring (see
``scripts/update_wasm.py``).
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import wasmtime

from . import _abi

if TYPE_CHECKING:
    from collections.abc import Callable

    from . import Bridge


def _build_handlers(bridge: Bridge) -> dict[str, Callable[..., str | None]]:
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

    return {
        "__wbg_getRandomValues_e9de607763a970bd": get_random_values,
        "__wbg___wbindgen_throw_be289d5034ed271b": throw_panic,
        "__wbg_Error_8c4e43fe74559d73": make_error,
        "__wbindgen_init_externref_table": externref_table_init,
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
