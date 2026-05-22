"""Confirm ``WasmCryptoProvider`` satisfies the ``CryptoProvider`` Protocol."""

from __future__ import annotations

from ootle._crypto import CryptoProvider, load_default_provider
from ootle._crypto._bridge import load_default_bridge
from ootle._crypto._wasm_provider import WasmCryptoProvider


def _accept(provider: CryptoProvider) -> CryptoProvider:
    """Static-typing accept site: pyright fails if WasmCryptoProvider drifts."""
    return provider


def test_wasm_crypto_provider_is_a_crypto_provider() -> None:
    provider = WasmCryptoProvider.load_default()
    assert _accept(provider) is provider


def test_load_default_provider_shares_underlying_bridge() -> None:
    a = load_default_provider()
    b = load_default_provider()
    assert isinstance(a, WasmCryptoProvider)
    assert isinstance(b, WasmCryptoProvider)
    # The wrapper is a thin, cheap-to-construct view; the thread-safe
    # singleton lives one layer down in ``_bridge``.
    assert load_default_bridge() is load_default_bridge()
