"""``OneTimePublicKey`` — the 32-byte Ristretto stealth spending key.

Mirrors Rust ``RistrettoPublicKeyBytes`` when used as a stealth UTXO's
``SpendCondition::Signed(pk)`` discriminant. Lives in its own module so
the requirement / statement / output modules can import it without
pulling the whole encrypted-data layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Self

from ootle._types.stealth._json import bytes_to_hex

# Ristretto public keys are 32-byte canonical encodings. The engine's
# ``RistrettoPublicKeyBytes`` type pins this length.
ONE_TIME_PUBLIC_KEY_LENGTH: Final[int] = 32


@dataclass(frozen=True, slots=True)
class OneTimePublicKey:
    """A 32-byte Ristretto public key used as a stealth spending key.

    The bytes are the canonical Ristretto encoding (``ristretto255``
    compressed form). The crypto provider derives these via DH from the
    recipient's view key.
    """

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != ONE_TIME_PUBLIC_KEY_LENGTH:
            msg = (
                f"OneTimePublicKey must be exactly {ONE_TIME_PUBLIC_KEY_LENGTH} bytes, "
                f"got {len(self.raw)}"
            )
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: object) -> Self:
        """Decode a hex string."""
        if not isinstance(data, str):
            msg = f"OneTimePublicKey must be a hex string, got {type(data).__name__}"
            raise TypeError(msg)
        decoded = bytes.fromhex(data)
        return cls(raw=decoded)

    def to_json(self) -> str:
        """Encode as lower-case hex (Rust ``serde`` shape)."""
        return bytes_to_hex(self.raw)
