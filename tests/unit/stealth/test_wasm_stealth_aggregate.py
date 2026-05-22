"""Real-WASM stealth provider: ``aggregate_input_masks``.

Pins the contract of the ``aggregateInputMasks`` export — a little-endian
Ristretto scalar sum over N 32-byte masks. The empty and single-mask
cases must match what the authorizer's single-input fast path relies on
(``masks[0]`` returned unchanged, no WASM round-trip).
"""

from __future__ import annotations

import pytest

from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle._types.stealth import Mask
from ootle.errors import CryptoBridgeError

_ZERO = b"\x00" * 32


def _scalar(n: int) -> Mask:
    """A canonical little-endian Ristretto scalar holding the small value ``n``."""
    return Mask(n.to_bytes(32, "little"))


def test_aggregate_empty_returns_zero_scalar(provider: WasmCryptoProvider) -> None:
    assert provider.aggregate_input_masks([]).raw == _ZERO


def test_aggregate_single_returns_mask_unchanged(provider: WasmCryptoProvider) -> None:
    mask = _scalar(7)
    assert provider.aggregate_input_masks([mask]) == mask


def test_aggregate_sums_masks_little_endian(provider: WasmCryptoProvider) -> None:
    result = provider.aggregate_input_masks([_scalar(1), _scalar(2)])
    assert result == _scalar(3)


def test_aggregate_is_commutative(provider: WasmCryptoProvider) -> None:
    a, _ = provider.generate_keypair()
    b, _ = provider.generate_keypair()
    forward = provider.aggregate_input_masks([Mask(a), Mask(b)])
    reverse = provider.aggregate_input_masks([Mask(b), Mask(a)])
    assert forward == reverse


def test_aggregate_rejects_non_canonical_scalar(provider: WasmCryptoProvider) -> None:
    with pytest.raises(CryptoBridgeError):
        provider.aggregate_input_masks([Mask(b"\xff" * 32)])
