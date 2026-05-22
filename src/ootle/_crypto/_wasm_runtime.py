"""WASM runtime loader.

Loads the vendored ``ootle_wasm_bg.wasm`` blob, verifies its SHA-256
against the committed ``VERSION`` metadata, and instantiates a single
process-wide ``wasmtime`` Engine + Store + Module + Instance.

Layers 1-3 never touch ``wasmtime`` directly — this module is the only
place that imports it.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files

import wasmtime

from ootle.errors import CryptoBridgeError

logger = logging.getLogger(__name__)

WASM_PKG = "ootle._crypto.wasm"
WASM_FILENAME = "ootle_wasm_bg.wasm"
VERSION_FILENAME = "VERSION"

ImportProvider = Callable[[wasmtime.Store, wasmtime.Module, wasmtime.Linker], None]
"""Callback that defines all ``__wbg_*`` host imports on a Linker.

Wired by ``_crypto._bridge`` in M0.T4. The runtime stays agnostic to the
specific bridge implementation.
"""


@dataclass(frozen=True, slots=True)
class _Version:
    upstream: str
    sha256: str
    fetched: str
    source: str


_VERSION_LINE_COUNT = 4


def _parse_version(text: str) -> _Version:
    """Parse the four ``key:value`` lines of the ``VERSION`` file by index."""
    lines = text.splitlines()
    if len(lines) < _VERSION_LINE_COUNT:
        msg = f"VERSION must have {_VERSION_LINE_COUNT} lines, got {len(lines)}"
        raise CryptoBridgeError(msg, context="VERSION parse")
    try:
        return _Version(
            upstream=lines[0].split(":", 1)[1].strip(),
            sha256=lines[1].split(":", 1)[1].strip(),
            fetched=lines[2].split(":", 1)[1].strip(),
            source=lines[3].split(":", 1)[1].strip(),
        )
    except IndexError as exc:
        raise CryptoBridgeError(
            f"VERSION line malformed: {exc}",
            context="VERSION parse",
        ) from exc


def _read_version() -> _Version:
    text = (files(WASM_PKG) / VERSION_FILENAME).read_text(encoding="utf-8")
    return _parse_version(text)


def _read_blob() -> bytes:
    return (files(WASM_PKG) / WASM_FILENAME).read_bytes()


def load_blob() -> tuple[bytes, _Version]:
    """Read the vendored blob and assert ``sha256(blob) == VERSION.sha256``."""
    version = _read_version()
    blob = _read_blob()
    actual = hashlib.sha256(blob).hexdigest()
    if not hmac.compare_digest(actual, version.sha256):
        logger.error(
            "WASM blob SHA-256 mismatch: upstream=%s expected=%s actual=%s",
            version.upstream,
            version.sha256,
            actual,
        )
        raise CryptoBridgeError(
            f"WASM blob SHA-256 mismatch: expected {version.sha256}, got {actual}",
            context="blob verify",
        )
    logger.debug(
        "WASM blob loaded: upstream=%s sha256=%s size=%d",
        version.upstream,
        version.sha256,
        len(blob),
    )
    return blob, version


@dataclass(slots=True)
class WasmRuntime:
    """Single-instance handle to the loaded WASM module."""

    engine: wasmtime.Engine
    store: wasmtime.Store
    module: wasmtime.Module
    instance: wasmtime.Instance
    memory: wasmtime.Memory
    version: _Version

    @classmethod
    def load(cls, *, define_imports: ImportProvider | None = None) -> WasmRuntime:
        """Load, verify, and instantiate the vendored blob.

        Args:
            define_imports: Callback that registers the ``__wbg_*`` host
                imports on the Linker. ``None`` installs ``NotImplementedError``
                stubs — useful only for the M0.T3 smoke path where exports
                are not yet called.
        """
        blob, version = load_blob()
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        module = wasmtime.Module(engine, blob)
        linker = wasmtime.Linker(engine)
        if define_imports is None:
            _install_stub_imports(store, module, linker)
        else:
            define_imports(store, module, linker)
        instance = linker.instantiate(store, module)
        memory_export = instance.exports(store).get("memory")
        if not isinstance(memory_export, wasmtime.Memory):
            raise CryptoBridgeError(
                "WASM module is missing the expected `memory` export",
                context="instantiate",
            )
        return cls(
            engine=engine,
            store=store,
            module=module,
            instance=instance,
            memory=memory_export,
            version=version,
        )


def _stub(name: str) -> Callable[..., object]:
    def _raise(*_args: object) -> object:
        msg = f"WASM import {name!r} called before bridge wiring (M0.T4)"
        raise NotImplementedError(msg)

    return _raise


def _install_stub_imports(
    store: wasmtime.Store, module: wasmtime.Module, linker: wasmtime.Linker
) -> None:
    """Register stubs for every host import declared by the module."""
    for imp in module.imports:
        if not isinstance(imp.type, wasmtime.FuncType):
            continue
        name = imp.name or "<anonymous>"
        module_name = imp.module or ""
        func = wasmtime.Func(store, imp.type, _stub(name))
        linker.define(store, module_name, name, func)
