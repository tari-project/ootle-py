"""Engine-side stealth UTXO substate carriers.

Distinct from the *send-side* :mod:`ootle._types.stealth._unspent` types, which
mirror ``template_lib_types::UnspentOutput`` — the shape we put *into* an
outgoing ``StealthTransferStatement``. This module mirrors the *persisted
substate* the indexer returns: ``engine_types::Utxo`` → ``UtxoOutput`` →
``OutputBody`` (``crates/engine_types/src/crypto/output.rs``).

The two shapes differ on the wire:

- the body carries ``public_nonce`` (not ``sender_public_nonce``);
- there is **no commitment** in the body — it is derived and lives in the
  substate id (``utxo_<resource>_<commitment_hex>``);
- ``viewable_balance`` is the 2-field ElGamal ciphertext
  (``ElgamalVerifiableBalanceBytes``) the engine keeps for viewable resources;
  the full :class:`ViewableBalanceProof` is verified at submission and dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Self

from ootle._types.stealth._json import hex_field, optional_dict, require_int
from ootle._types.stealth.encrypted_data import EncryptedData

_RISTRETTO_PUBLIC_KEY_LEN: Final[int] = 32


@dataclass(frozen=True, slots=True)
class ElgamalVerifiableBalance:
    """On-chain ElGamal viewable-balance ciphertext (``ElgamalVerifiableBalanceBytes``).

    Only the ``encrypted`` + ``public_nonce`` ciphertext is persisted; the
    decryption is ``V = encrypted - view_secret * public_nonce`` plus a
    brute-force lookup. The proof-of-correctness fields of the send-side
    :class:`ViewableBalanceProof` are not stored.
    """

    encrypted: bytes
    public_nonce: bytes

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            encrypted=hex_field(data, "encrypted", length=_RISTRETTO_PUBLIC_KEY_LEN),
            public_nonce=hex_field(data, "public_nonce", length=_RISTRETTO_PUBLIC_KEY_LEN),
        )


@dataclass(frozen=True, slots=True)
class StealthOutputBody:
    """Engine substate UTXO body (``engine_types::crypto::OutputBody``).

    The commitment is *not* a field — derive it from the substate id. Use
    :meth:`from_json` on the inner ``Utxo.output.output`` object.
    """

    public_nonce: bytes
    encrypted_data: EncryptedData
    minimum_value_promise: int
    viewable_balance: ElgamalVerifiableBalance | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        encrypted = data.get("encrypted_data")
        if not isinstance(encrypted, str):
            msg = "encrypted_data must be a hex string"
            raise TypeError(msg)
        vb = optional_dict(data, "viewable_balance")
        return cls(
            public_nonce=hex_field(data, "public_nonce", length=_RISTRETTO_PUBLIC_KEY_LEN),
            encrypted_data=EncryptedData.from_json(encrypted),
            minimum_value_promise=require_int(data, "minimum_value_promise"),
            viewable_balance=None if vb is None else ElgamalVerifiableBalance.from_json(vb),
        )
