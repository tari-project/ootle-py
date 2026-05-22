"""Fixtures for the real-WASM stealth provider tests."""

from __future__ import annotations

import pytest

from ootle._crypto._wasm_provider import WasmCryptoProvider


@pytest.fixture
def provider() -> WasmCryptoProvider:
    """A crypto provider over the singleton WASM bridge, with stealth methods."""
    return WasmCryptoProvider.load_default()
