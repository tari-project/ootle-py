"""Bridge between Python and the vendored ``ootle-wasm`` blob.

Public surface (used by ``_wasm_provider``):

- :class:`Bridge` — handle bundling the runtime, exports, panic state, and
  the ABI helpers needed to call WASM exports.
- :func:`load_default_bridge` — process-wide cached factory.
- :func:`define_imports` — passed to :func:`WasmRuntime.load` to wire
  ``__wbg_*`` host imports onto the linker.

This module is *internal*. No name exposed here is part of ``ootle``'s
public API.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import wasmtime

from ootle._crypto._wasm_runtime import WasmRuntime

from ._imports import define_imports

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(slots=True)
class Bridge:
    """Mutable handle the host imports close over.

    Constructed empty, populated post-instantiation by :meth:`load_default`.
    The mutability is required because the host imports are defined
    *before* the WASM module is instantiated, but they need access to
    the resulting :class:`wasmtime.Memory` and exports map.
    """

    runtime: WasmRuntime | None = None
    panic_message: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def store(self) -> wasmtime.Store:
        return self._runtime.store

    @property
    def memory(self) -> wasmtime.Memory:
        return self._runtime.memory

    @property
    def exports(self) -> Mapping[str, Any]:
        return self._runtime.instance.exports(self._runtime.store)

    @property
    def _runtime(self) -> WasmRuntime:
        if self.runtime is None:
            msg = "Bridge used before runtime was attached"
            raise RuntimeError(msg)
        return self.runtime

    def consume_panic(self) -> str | None:
        msg = self.panic_message
        self.panic_message = None
        return msg

    @classmethod
    def load_default(cls) -> Bridge:
        """Load the vendored blob and wire every host import."""
        bridge = cls()

        def _wire(store: wasmtime.Store, module: wasmtime.Module, linker: wasmtime.Linker) -> None:
            define_imports(store, module, linker, bridge)

        bridge.runtime = WasmRuntime.load(define_imports=_wire)
        # wasm-bindgen places initial setup behind an explicit start export.
        start = bridge.exports["__wbindgen_start"]
        if not isinstance(start, wasmtime.Func):
            msg = "WASM module is missing the __wbindgen_start export"
            raise RuntimeError(msg)
        start(bridge.store)
        return bridge


_singleton_lock = threading.Lock()
_singleton: Bridge | None = None


def load_default_bridge() -> Bridge:
    """Return the process-wide singleton bridge.

    Double-checked locking — ``functools.cache`` is not safe for the
    *first* call when multiple threads race; wasmtime drops the GIL
    inside ``Module``/``Instance`` construction, so two racers would
    each instantiate a separate engine and one would be silently
    discarded with native resources still attached.
    """
    global _singleton  # noqa: PLW0603 - module-level cache
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = Bridge.load_default()
        return _singleton


__all__ = ["Bridge", "load_default_bridge"]
