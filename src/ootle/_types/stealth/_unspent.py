"""Engine-level stealth UTXO carriers.

Mirrors ``crates/template_lib_types/src/stealth/unspent_output.rs``:

- :class:`UnspentOutput` — the body of a stealth UTXO (commitment,
  sender nonce, encrypted data, minimum-value promise, optional
  viewable-balance proof).
- :class:`StealthUnspentOutput` — UTXO body + spend condition + UTXO
  tag, the shape an output statement carries.

The ``spend_condition`` is round-tripped as a raw dict so callers own
the discriminated-union shape — Python ``match`` works naturally on
string keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Self

from ootle._types.stealth._json import (
    bytes_to_hex,
    hex_field,
    hex_to_bytes,
    optional_dict,
    require_dict,
    require_int,
)
from ootle._types.stealth._proofs import ViewableBalanceProof
from ootle._types.stealth.encrypted_data import EncryptedData

_RISTRETTO_PUBLIC_KEY_LEN: Final[int] = 32
_PEDERSEN_COMMITMENT_LEN: Final[int] = 32
_U32_MAX: Final[int] = 0xFFFF_FFFF


@dataclass(frozen=True, slots=True)
class UnspentOutput:
    """Engine-visible stealth UTXO body."""

    commitment: bytes
    sender_public_nonce: bytes
    encrypted_data: EncryptedData
    minimum_value_promise: int
    viewable_balance_proof: ViewableBalanceProof | None = None

    def __post_init__(self) -> None:
        if len(self.commitment) != _PEDERSEN_COMMITMENT_LEN:
            msg = f"commitment must be {_PEDERSEN_COMMITMENT_LEN} bytes, got {len(self.commitment)}"
            raise ValueError(msg)
        if len(self.sender_public_nonce) != _RISTRETTO_PUBLIC_KEY_LEN:
            msg = (
                f"sender_public_nonce must be {_RISTRETTO_PUBLIC_KEY_LEN} bytes, "
                f"got {len(self.sender_public_nonce)}"
            )
            raise ValueError(msg)
        if self.minimum_value_promise < 0:
            msg = "minimum_value_promise must be non-negative"
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        encrypted = data.get("encrypted_data")
        if not isinstance(encrypted, str):
            msg = "encrypted_data must be a hex string"
            raise TypeError(msg)
        vbp = optional_dict(data, "viewable_balance_proof")
        return cls(
            commitment=hex_field(data, "commitment", length=_PEDERSEN_COMMITMENT_LEN),
            sender_public_nonce=hex_field(
                data, "sender_public_nonce", length=_RISTRETTO_PUBLIC_KEY_LEN
            ),
            encrypted_data=EncryptedData(raw=hex_to_bytes(encrypted)),
            minimum_value_promise=require_int(data, "minimum_value_promise"),
            viewable_balance_proof=None if vbp is None else ViewableBalanceProof.from_json(vbp),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "commitment": bytes_to_hex(self.commitment),
            "sender_public_nonce": bytes_to_hex(self.sender_public_nonce),
            "encrypted_data": self.encrypted_data.to_json(),
            "minimum_value_promise": self.minimum_value_promise,
            "viewable_balance_proof": (
                None
                if self.viewable_balance_proof is None
                else self.viewable_balance_proof.to_json()
            ),
        }


@dataclass(frozen=True, slots=True)
class StealthUnspentOutput:
    """Stealth UTXO envelope: body + spend condition + UTXO tag."""

    output: UnspentOutput
    spend_condition: dict[str, Any]
    tag: int

    def __post_init__(self) -> None:
        if self.tag < 0 or self.tag > _U32_MAX:
            msg = f"tag must fit in a u32, got {self.tag}"
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            output=UnspentOutput.from_json(require_dict(data, "output")),
            spend_condition=require_dict(data, "spend_condition"),
            tag=require_int(data, "tag"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "output": self.output.to_json(),
            "spend_condition": self.spend_condition,
            "tag": self.tag,
        }
