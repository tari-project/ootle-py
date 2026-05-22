"""Crypto-proof carriers used by stealth statements.

These wrap byte-payload-only Rust types (Schnorr balance-proof
signatures and ElGamal viewable-balance proofs). They do not verify
the cryptographic relations — that is the engine's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Self

from ootle._types.stealth._json import bytes_to_hex, hex_field

_RISTRETTO_PUBLIC_KEY_LEN: Final[int] = 32
_PEDERSEN_COMMITMENT_LEN: Final[int] = 32
_SCALAR_LEN: Final[int] = 32


@dataclass(frozen=True, slots=True)
class BalanceProofSignature:
    """Schnorr signature: ``(public_nonce, signature)`` — 64 bytes total.

    Mirrors Rust ``SchnorrSignatureBytes`` (aliased ``BalanceProofSignature``).
    """

    public_nonce: bytes
    signature: bytes

    def __post_init__(self) -> None:
        if len(self.public_nonce) != _RISTRETTO_PUBLIC_KEY_LEN:
            msg = (
                f"public_nonce must be {_RISTRETTO_PUBLIC_KEY_LEN} bytes, "
                f"got {len(self.public_nonce)}"
            )
            raise ValueError(msg)
        if len(self.signature) != _SCALAR_LEN:
            msg = f"signature must be {_SCALAR_LEN} bytes, got {len(self.signature)}"
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            public_nonce=hex_field(data, "public_nonce", length=_RISTRETTO_PUBLIC_KEY_LEN),
            signature=hex_field(data, "signature", length=_SCALAR_LEN),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "public_nonce": bytes_to_hex(self.public_nonce),
            "signature": bytes_to_hex(self.signature),
        }


@dataclass(frozen=True, slots=True)
class ViewableBalanceProof:
    """ElGamal viewable-balance proof — 8 32-byte field carrier.

    Mirrors ``template_lib::stealth::ViewableBalanceProof``.
    """

    elgamal_encrypted: bytes
    elgamal_public_nonce: bytes
    c_prime: bytes
    e_prime: bytes
    r_prime: bytes
    s_v: bytes
    s_m: bytes
    s_r: bytes

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            elgamal_encrypted=hex_field(
                data, "elgamal_encrypted", length=_RISTRETTO_PUBLIC_KEY_LEN
            ),
            elgamal_public_nonce=hex_field(
                data, "elgamal_public_nonce", length=_RISTRETTO_PUBLIC_KEY_LEN
            ),
            c_prime=hex_field(data, "c_prime", length=_PEDERSEN_COMMITMENT_LEN),
            e_prime=hex_field(data, "e_prime", length=_RISTRETTO_PUBLIC_KEY_LEN),
            r_prime=hex_field(data, "r_prime", length=_RISTRETTO_PUBLIC_KEY_LEN),
            s_v=hex_field(data, "s_v", length=_SCALAR_LEN),
            s_m=hex_field(data, "s_m", length=_SCALAR_LEN),
            s_r=hex_field(data, "s_r", length=_SCALAR_LEN),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "elgamal_encrypted": bytes_to_hex(self.elgamal_encrypted),
            "elgamal_public_nonce": bytes_to_hex(self.elgamal_public_nonce),
            "c_prime": bytes_to_hex(self.c_prime),
            "e_prime": bytes_to_hex(self.e_prime),
            "r_prime": bytes_to_hex(self.r_prime),
            "s_v": bytes_to_hex(self.s_v),
            "s_m": bytes_to_hex(self.s_m),
            "s_r": bytes_to_hex(self.s_r),
        }
