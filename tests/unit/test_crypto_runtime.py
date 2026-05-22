"""Tests for the WASM runtime loader."""

from __future__ import annotations

import pytest

from ootle._crypto import _wasm_runtime as rt
from ootle.errors import CryptoBridgeError


def test_load_blob_succeeds_and_returns_version() -> None:
    blob, version = rt.load_blob()
    assert blob.startswith(b"\x00asm")
    assert len(version.sha256) == 64


def test_load_with_stub_imports_instantiates() -> None:
    runtime = rt.WasmRuntime.load()
    assert runtime.memory is not None


def test_tampered_blob_raises_crypto_bridge_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "_read_blob", lambda: b"\x00asm\x00\x00\x00\x00bogus")
    with pytest.raises(CryptoBridgeError, match="SHA-256 mismatch"):
        rt.load_blob()


def test_tampered_version_raises_crypto_bridge_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rt, "_read_version", lambda: rt._parse_version("only one line\n"))  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(CryptoBridgeError, match="VERSION"):
        rt.load_blob()


def test_parse_version_rejects_short_input() -> None:
    with pytest.raises(CryptoBridgeError):
        rt._parse_version("upstream: 0.0.0\n")  # pyright: ignore[reportPrivateUsage]
