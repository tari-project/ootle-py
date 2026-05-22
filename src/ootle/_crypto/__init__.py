"""Crypto layer (Layer 6). Hosts the WASM bridge to ``@tari-project/ootle-wasm``.

Public re-exports here are the only symbols Layers 1-3 may use. Anything
else (``_bridge``, ``_wasm_runtime``, ``_wasm_provider``) is internal —
imports of those names from outside ``_crypto`` are not supported.

The thread-safe singleton lives in ``_bridge``; this module is a thin
wrapper that returns a fresh :class:`WasmCryptoProvider` over the
shared bridge on each call.
"""

from __future__ import annotations

from typing import cast

from ootle.errors import InvalidArgumentError

from ._provider import CryptoProvider, ParsedAddress, SchnorrSignatureResult
from ._stealth_provider import StealthCryptoProvider, StealthOutputsStatementResult
from ._wasm_provider import WasmCryptoProvider

# The full method set of ``StealthCryptoProvider`` — kept in lockstep with the
# (single, synchronous) Protocol so a partial caller-supplied provider fails at
# the boundary instead of with an opaque ``AttributeError`` mid-operation.
_STEALTH_METHODS = (
    "generate_outputs_statement",
    "generate_balance_proof_signature",
    "unblind_output",
    "aggregate_input_masks",
    "stealth_dh_secret",
    "validate_transfer",
)


def load_default_provider() -> CryptoProvider:
    """Return a crypto provider backed by the singleton WASM bridge.

    The underlying bridge is a process-wide singleton (see
    ``_bridge.load_default_bridge``); the returned provider is a thin
    wrapper that is cheap to construct. Tests can swap in a
    ``MockCryptoProvider`` by passing a different provider through the
    ``OotleClient`` constructor.
    """
    return WasmCryptoProvider.load_default()


def ensure_stealth_capable(crypto: object | None) -> CryptoProvider:
    """Resolve ``crypto`` into a stealth-capable provider.

    ``None`` defaults to the singleton WASM provider (which implements
    every stealth primitive natively). A non-``None`` provider missing the
    stealth surface raises :class:`~ootle.errors.InvalidArgumentError` —
    the caller wired a ``crypto=`` that cannot back stealth operations.
    Each call-site casts the result to the (sync or async) stealth
    Protocol it needs.
    """
    if crypto is None:
        return WasmCryptoProvider.load_default()
    missing = [name for name in _STEALTH_METHODS if not hasattr(crypto, name)]
    if missing:
        msg = f"configured CryptoProvider is missing stealth methods: {', '.join(missing)}"
        raise InvalidArgumentError(msg)
    return cast("CryptoProvider", crypto)


__all__ = [
    "CryptoProvider",
    "ParsedAddress",
    "SchnorrSignatureResult",
    "StealthCryptoProvider",
    "StealthOutputsStatementResult",
    "ensure_stealth_capable",
    "load_default_provider",
]
