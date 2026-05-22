"""``Output`` (stealth transfer destination) plus the ``Mask`` carrier.

Mirrors the upstream Rust ``ootle_rs::stealth::spec::Output``:

```rust
pub struct Output {
    pub destination: Address,
    pub amount: NonZeroU64,
    pub resource_address: ResourceAddress,
    pub resource_view_key: Option<RistrettoPublicKey>,
    pub memo: Option<Memo>,
    pub pay_to: PayTo,
    pub utxo_tag: Option<UtxoTag>,
    pub minimum_value_promise: u64,
}
```

The Python mirror:

- ``destination`` is the recipient :class:`~ootle._types.address.Address`.
- ``amount`` is enforced positive in ``__post_init__`` — Rust uses
  ``NonZeroU64`` for the same invariant.
- ``memo`` / ``pay_to`` are stored as raw mappings; the engine owns the
  Borsh-level shape, our job is to round-trip the JSON faithfully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final, Self

from ootle._types._json_helpers import require_str
from ootle._types.stealth._json import bytes_to_hex, require_int

if TYPE_CHECKING:
    from ootle._types.address import Address, ResourceAddress


# 32 bytes — matches the engine's ``Scalar32Bytes`` and ``SIZE_MASK``.
MASK_LENGTH: Final[int] = 32
_VIEW_KEY_LENGTH: Final[int] = 32
_U32_MAX: Final[int] = 0xFFFF_FFFF


@dataclass(frozen=True, slots=True)
class Mask:
    """Pedersen commitment mask: a 32-byte Ristretto scalar."""

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != MASK_LENGTH:
            msg = f"Mask must be exactly {MASK_LENGTH} bytes, got {len(self.raw)}"
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: object) -> Self:
        """Decode a hex string."""
        if not isinstance(data, str):
            msg = f"Mask must be a hex string, got {type(data).__name__}"
            raise TypeError(msg)
        return cls(raw=bytes.fromhex(data))

    def to_json(self) -> str:
        """Encode as lower-case hex."""
        return bytes_to_hex(self.raw)


def positive_amount(value: object) -> int:
    """Validate ``value`` is a positive ``int`` (``> 0``).

    Mirrors Rust ``NonZeroU64::new(value).ok_or(...)``. Returns the value
    unchanged on success; raises :class:`ValueError` otherwise.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"amount must be a positive int, got {type(value).__name__}"
        raise TypeError(msg)
    if value <= 0:
        msg = f"amount must be positive (> 0), got {value}"
        raise ValueError(msg)
    return value


@dataclass(frozen=True, slots=True)
class Output:
    """A stealth-transfer output destination.

    ``amount`` is required to be a positive integer (``NonZeroU64`` in
    Rust); ``__post_init__`` raises :class:`ValueError` on zero or
    negative values. The remaining fields default to ``None`` /
    ``StealthPublicKey`` to match Rust ``Output::new``.
    """

    destination: Address
    amount: int
    resource_address: ResourceAddress
    resource_view_key: bytes | None = None
    memo: dict[str, Any] | None = None
    pay_to: dict[str, Any] = field(default_factory=lambda: {"StealthPublicKey": {}})
    utxo_tag: int | None = None
    minimum_value_promise: int = 0

    def __post_init__(self) -> None:
        positive_amount(self.amount)
        if self.minimum_value_promise < 0:
            msg = f"minimum_value_promise must be non-negative, got {self.minimum_value_promise}"
            raise ValueError(msg)
        if self.resource_view_key is not None and len(self.resource_view_key) != _VIEW_KEY_LENGTH:
            msg = (
                f"resource_view_key must be exactly {_VIEW_KEY_LENGTH} bytes when provided, "
                f"got {len(self.resource_view_key)}"
            )
            raise ValueError(msg)
        if self.utxo_tag is not None and (self.utxo_tag < 0 or self.utxo_tag > _U32_MAX):
            msg = f"utxo_tag must fit in a u32, got {self.utxo_tag}"
            raise ValueError(msg)

    def to_json(self) -> dict[str, Any]:
        """Encode to the canonical ``Output`` wire shape."""
        out: dict[str, Any] = {
            "destination": self.destination.bech32m,
            "amount": self.amount,
            "resource_address": str(self.resource_address),
            "resource_view_key": (
                None if self.resource_view_key is None else bytes_to_hex(self.resource_view_key)
            ),
            "memo": self.memo,
            "pay_to": self.pay_to,
            "utxo_tag": self.utxo_tag,
            "minimum_value_promise": self.minimum_value_promise,
        }
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any], *, destination: Address) -> Self:
        """Parse an ``Output`` JSON object.

        ``destination`` is supplied by the caller because resolving an
        :class:`Address` requires the crypto bridge.
        """
        from ootle._types.address import ResourceAddress as _ResourceAddress  # noqa: PLC0415

        resource = _ResourceAddress(require_str(data, "resource_address"))
        view_key_raw = data.get("resource_view_key")
        view_key: bytes | None = None
        if view_key_raw is not None:
            if not isinstance(view_key_raw, str):
                msg = "resource_view_key must be a hex string when present"
                raise TypeError(msg)
            view_key = bytes.fromhex(view_key_raw)
        raw_pay_to = data.get("pay_to")
        default_pay_to: dict[str, Any] = {"StealthPublicKey": {}}
        pay_to: dict[str, Any] = raw_pay_to if raw_pay_to is not None else default_pay_to
        return cls(
            destination=destination,
            amount=require_int(data, "amount"),
            resource_address=resource,
            resource_view_key=view_key,
            memo=data.get("memo"),
            pay_to=pay_to,
            utxo_tag=data.get("utxo_tag"),
            minimum_value_promise=int(data.get("minimum_value_promise") or 0),
        )
