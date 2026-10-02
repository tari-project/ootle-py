"""``RevealedOutput`` — the revealed half of a stealth outputs statement.

Mirrors ``template_lib_types::stealth::RevealedOutput``: the revealed
amount plus the key whose badge must be in the transaction's auth scope
before the engine creates the revealed bucket. Binding the receiver means
a statement lifted into another transaction yields its revealed funds to
nobody.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Self

from ootle._types.stealth._json import bytes_to_hex, hex_field, require_amount

_RISTRETTO_PUBLIC_KEY_LEN: Final[int] = 32


@dataclass(frozen=True, slots=True)
class RevealedOutput:
    """A positive revealed amount and the 32-byte public key authorised to take it."""

    amount: int
    receiver: bytes

    def __post_init__(self) -> None:
        if self.amount <= 0:
            msg = f"RevealedOutput.amount must be positive, got {self.amount}"
            raise ValueError(msg)
        if len(self.receiver) != _RISTRETTO_PUBLIC_KEY_LEN:
            msg = (
                f"RevealedOutput.receiver must be {_RISTRETTO_PUBLIC_KEY_LEN} bytes, "
                f"got {len(self.receiver)}"
            )
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            amount=require_amount(data, "amount"),
            receiver=hex_field(data, "receiver", length=_RISTRETTO_PUBLIC_KEY_LEN),
        )

    def to_json(self) -> dict[str, Any]:
        return {"amount": self.amount, "receiver": bytes_to_hex(self.receiver)}
