"""``ensure_stealth_capable`` — boundary guard for caller-supplied ``crypto=``.

The guard must reject a provider missing *any* of the stealth methods, not
just the first one it happens to probe, and name the gap in the error.
"""

from __future__ import annotations

import pytest

from ootle._crypto import ensure_stealth_capable
from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle.errors import InvalidArgumentError

# The methods the guard requires; mirrors the (single) StealthCryptoProvider.
_STEALTH_METHODS = (
    "generate_outputs_statement",
    "generate_balance_proof_signature",
    "unblind_output",
    "aggregate_input_masks",
    "stealth_dh_secret",
    "validate_transfer",
)


def _noop(*_args: object, **_kwargs: object) -> None:
    """Placeholder stub method — the guard only probes for presence."""


def _stub_with(methods: tuple[str, ...]) -> object:
    """Build an object exposing exactly ``methods`` as callables."""
    namespace: dict[str, object] = dict.fromkeys(methods, _noop)
    return type("CryptoStub", (), namespace)()


def test_none_defaults_to_wasm_provider() -> None:
    assert isinstance(ensure_stealth_capable(None), WasmCryptoProvider)


def test_full_provider_passes_through() -> None:
    stub = _stub_with(_STEALTH_METHODS)
    assert ensure_stealth_capable(stub) is stub


def test_real_wasm_provider_is_stealth_capable() -> None:
    provider = WasmCryptoProvider.load_default()
    assert ensure_stealth_capable(provider) is provider


@pytest.mark.parametrize("omit", _STEALTH_METHODS)
def test_provider_missing_any_method_is_rejected(omit: str) -> None:
    """Dropping *any* single stealth method must trip the boundary guard."""
    present = tuple(name for name in _STEALTH_METHODS if name != omit)
    with pytest.raises(InvalidArgumentError) as exc:
        ensure_stealth_capable(_stub_with(present))
    assert omit in str(exc.value)


def test_error_lists_all_missing_methods() -> None:
    """An empty object is missing every method; the error names them all."""
    with pytest.raises(InvalidArgumentError) as exc:
        ensure_stealth_capable(object())
    message = str(exc.value)
    for method in _STEALTH_METHODS:
        assert method in message
