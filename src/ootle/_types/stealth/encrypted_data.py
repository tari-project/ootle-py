"""``EncryptedData`` and ``DecryptedData`` carriers.

``EncryptedData`` is the AEAD-encrypted (mask, value, memo) payload that
travels with every stealth UTXO. The Rust upstream stores it as
``MaxBytes<MAX_SIZE>`` — a sized byte slice with a min/max range. We
mirror the same range constants and wrap the bytes in a frozen
dataclass.

``DecryptedData`` is the wallet-side counterpart returned after the
crypto provider decrypts an input. It carries the mask, the µTari value,
and an optional memo. None of these helpers touch crypto themselves —
the provider does the work and returns the typed result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Self

from ootle._types.stealth._json import bytes_to_hex, hex_field, optional_hex_field, require_int

# Mirrors ``EncryptedData`` constants in
# crates/template_lib_types/src/encrypted_data.rs:
#   SIZE_NONCE = 24, SIZE_VALUE = 8, SIZE_MASK = 32, SIZE_TAG = 16
# Total without memo = 80; MAX_MEMO_SIZE = 255 → MAX_SIZE = 335.
SIZE_TAG: Final[int] = 16
SIZE_NONCE: Final[int] = 24
SIZE_VALUE: Final[int] = 8
SIZE_MASK: Final[int] = 32
MAX_MEMO_SIZE: Final[int] = 255
ENCRYPTED_DATA_SIZE_WITHOUT_MEMO: Final[int] = SIZE_NONCE + SIZE_VALUE + SIZE_MASK + SIZE_TAG
MAX_ENCRYPTED_DATA_SIZE: Final[int] = ENCRYPTED_DATA_SIZE_WITHOUT_MEMO + MAX_MEMO_SIZE


@dataclass(frozen=True, slots=True)
class EncryptedData:
    """Opaque AEAD-encrypted ``(mask, value, memo)`` blob.

    The byte layout — ``[tag || nonce || ciphertext]`` — is owned by the
    engine. We expose only the raw bytes here; the crypto provider ships
    them in and out as hex.
    """

    raw: bytes

    def __post_init__(self) -> None:
        n = len(self.raw)
        if n != 0 and (n < ENCRYPTED_DATA_SIZE_WITHOUT_MEMO or n > MAX_ENCRYPTED_DATA_SIZE):
            msg = (
                f"EncryptedData payload size {n} outside the allowed range "
                f"[{ENCRYPTED_DATA_SIZE_WITHOUT_MEMO}..{MAX_ENCRYPTED_DATA_SIZE}]"
            )
            raise ValueError(msg)

    @classmethod
    def empty(cls) -> Self:
        """Match Rust's ``EncryptedData::empty``."""
        return cls(raw=b"")

    @property
    def is_empty(self) -> bool:
        """``True`` when no ciphertext is attached."""
        return len(self.raw) == 0

    @classmethod
    def from_json(cls, data: object) -> Self:
        """Decode a hex string carrier into an :class:`EncryptedData`."""
        if not isinstance(data, str):
            msg = f"EncryptedData payload must be a hex string, got {type(data).__name__}"
            raise TypeError(msg)
        return cls(raw=bytes.fromhex(data))

    def to_json(self) -> str:
        """Encode the blob as lower-case hex (Rust ``serde`` shape)."""
        return bytes_to_hex(self.raw)


@dataclass(frozen=True, slots=True)
class DecryptedData:
    """Wallet-side cleartext of an ``EncryptedData`` carrier.

    Mirrors the ``decrypt_input_data`` reply shape:
    ``{mask: hex, value: int, memo: hex | null}``. ``mask`` is a
    32-byte Ristretto scalar; ``value`` is the µTari amount.
    """

    mask: bytes
    value: int
    memo: bytes | None = None

    def __post_init__(self) -> None:
        if len(self.mask) != SIZE_MASK:
            msg = f"DecryptedData.mask must be exactly {SIZE_MASK} bytes, got {len(self.mask)}"
            raise ValueError(msg)
        if self.value < 0:
            msg = f"DecryptedData.value must be non-negative, got {self.value}"
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        """Parse the ``decrypt_input_data`` response shape."""
        return cls(
            mask=hex_field(data, "mask", length=SIZE_MASK),
            value=require_int(data, "value"),
            memo=optional_hex_field(data, "memo"),
        )

    def to_json(self) -> dict[str, Any]:
        """Encode to the canonical ``{mask, value, memo}`` shape."""
        out: dict[str, Any] = {"mask": bytes_to_hex(self.mask), "value": self.value}
        out["memo"] = None if self.memo is None else bytes_to_hex(self.memo)
        return out
