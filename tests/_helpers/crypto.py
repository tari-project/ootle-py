"""Test helpers around the crypto layer.

``MockCryptoProvider`` is a deterministic, **non-cryptographic**
implementation of :class:`CryptoProvider`. Outputs are derived from
SHA-256 of input concatenations so tests get stable values without
needing the WASM bridge. Never use this in production.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ootle._crypto import ParsedAddress, SchnorrSignatureResult


def _sha(*parts: bytes | str | int) -> bytes:
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, int):
            h.update(part.to_bytes(8, "little", signed=False))
        elif isinstance(part, str):
            h.update(part.encode("utf-8"))
        else:
            h.update(part)
    return h.digest()


@dataclass(slots=True)
class MockCryptoProvider:
    """Deterministic stand-in for tests that don't need wire authenticity."""

    seed: bytes = b"mock-crypto-seed"
    _counter: int = 0

    def _next(self, label: str) -> bytes:
        self._counter += 1
        return _sha(self.seed, label, self._counter)

    def generate_keypair(self) -> tuple[bytes, bytes]:
        sk = self._next("kp_sk")
        return sk, _sha(b"pk_from", sk)

    def generate_ootle_secret_key(self) -> tuple[bytes, bytes]:
        return self._next("ootle_owner_sk"), self._next("ootle_view_sk")

    def public_key_from_secret(self, sk: bytes) -> bytes:
        return _sha(b"pk_from", sk)

    def ootle_public_key_from_secret(self, owner: bytes, view: bytes) -> tuple[bytes, bytes]:
        return _sha(b"opk_owner", owner), _sha(b"opk_view", view)

    def generate_ootle_address(
        self,
        owner_pk: bytes,
        view_pk: bytes,
        network: int,
        memo: bytes | None = None,
    ) -> str:
        digest = _sha(b"addr", owner_pk, view_pk, network, memo or b"")
        return "otl_mock_" + digest.hex()

    def parse_ootle_address(self, address: str) -> ParsedAddress:
        if not address.startswith("otl_mock_"):
            raise ValueError(f"unrecognised mock address: {address!r}")
        digest = bytes.fromhex(address.removeprefix("otl_mock_"))
        return ParsedAddress(
            owner_key=_sha(b"opk_owner", digest),
            view_key=_sha(b"opk_view", digest),
            network=0,
            memo=None,
        )

    def schnorr_sign(self, sk: bytes, message: bytes) -> SchnorrSignatureResult:
        nonce = _sha(b"nonce", sk, message)
        return SchnorrSignatureResult(
            public_nonce=nonce,
            signature=_sha(b"sig", sk, nonce, message),
        )

    def hash_unsigned_transaction(self, unsigned_json: str, seal_pk: bytes) -> bytes:
        return _sha(b"hash_tx", unsigned_json, seal_pk)

    def add_transaction_signer(self, tx_json: str, signer_sk: bytes, seal_pk: bytes) -> str:
        marker = _sha(b"signer", signer_sk, seal_pk).hex()
        return f'{{"prev":{tx_json},"signer":"{marker}"}}'

    def stealth_dh_secret(
        self, network_byte: int, owner_secret: bytes, public_nonce: bytes
    ) -> bytes:
        return _sha(b"stealth_dh", network_byte, owner_secret, public_nonce)

    def seal_transaction(self, tx_json: str, seal_sk: bytes) -> str:
        marker = _sha(b"seal", seal_sk).hex()
        return f'{{"sealed":{tx_json},"seal":"{marker}"}}'

    def bor_encode_transaction(self, transaction_json: str) -> str:
        return _sha(b"bor", transaction_json).hex()
