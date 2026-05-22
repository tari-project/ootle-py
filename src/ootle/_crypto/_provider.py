"""``CryptoProvider`` Protocol and the value types it returns.

The Protocol is the **only** seam Layers 1-3 may use to talk to the
WASM bridge. ``WasmCryptoProvider`` is the production implementation
(see ``_wasm_provider``); test code wires a ``MockCryptoProvider``.

Split-Protocol decision (stealth workstream)
--------------------------------------------

Stealth crypto primitives (bulletproofs, ElGamal viewable balance,
AEAD-encrypted outputs, stealth DH KDFs) live on a separate Protocol —
see :class:`~ootle._crypto._stealth_provider.StealthCryptoProvider`.
Both Protocols are synchronous; the WASM work behind them runs behind a
lock with no I/O of its own.

The split is by responsibility, not by sync/async: stealth is a distinct,
optional surface, so non-stealth callers depend only on the smaller
:class:`CryptoProvider` Protocol.

- :class:`CryptoProvider` — the base WASM-backed surface.
- :class:`~ootle._crypto._stealth_provider.StealthCryptoProvider` —
  the stealth surface. The sole implementation is
  :class:`WasmCryptoProvider`, which satisfies both Protocols natively.

The ``_async/`` callers offload these synchronous calls onto a worker
thread so the event loop is not blocked; the generated ``_sync/`` callers
invoke them directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SchnorrSignatureResult:
    """Output of :meth:`CryptoProvider.schnorr_sign`."""

    public_nonce: bytes
    signature: bytes


@dataclass(frozen=True, slots=True)
class ParsedAddress:
    """Output of :meth:`CryptoProvider.parse_ootle_address`."""

    owner_key: bytes
    view_key: bytes
    network: int
    memo: bytes | None


class CryptoProvider(Protocol):
    """The single seam between Layers 1-3 and the WASM crypto blob.

    Method signatures mirror ``@tari-project/ootle-wasm``'s ``.d.ts``
    one-for-one. Implementations must be safe to call concurrently from
    multiple threads (the WASM Store itself is not thread-safe — use a
    lock).
    """

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate a fresh Ristretto keypair. Returns ``(secret_key, public_key)``."""
        ...

    def generate_ootle_secret_key(self) -> tuple[bytes, bytes]:
        """Generate a fresh ``(owner_secret, view_secret)`` Ootle keypair."""
        ...

    def public_key_from_secret(self, sk: bytes) -> bytes:
        """Derive the Ristretto public key from a 32-byte secret key."""
        ...

    def ootle_public_key_from_secret(self, owner: bytes, view: bytes) -> tuple[bytes, bytes]:
        """Derive ``(owner_public, view_public)`` from a pair of secret keys."""
        ...

    def generate_ootle_address(
        self,
        owner_pk: bytes,
        view_pk: bytes,
        network: int,
        memo: bytes | None = None,
    ) -> str:
        """Produce a bech32m Ootle address string."""
        ...

    def parse_ootle_address(self, address: str) -> ParsedAddress:
        """Decode a bech32m Ootle address into its byte components."""
        ...

    def schnorr_sign(self, sk: bytes, message: bytes) -> SchnorrSignatureResult:
        """Schnorr-sign ``message`` with ``sk`` (Ristretto)."""
        ...

    def hash_unsigned_transaction(self, unsigned_json: str, seal_pk: bytes) -> bytes:
        """Return the 64-byte signing message for an unsigned transaction."""
        ...

    def add_transaction_signer(self, tx_json: str, signer_sk: bytes, seal_pk: bytes) -> str:
        """Append a signature to an unsigned/unsealed transaction. Returns JSON."""
        ...

    def seal_transaction(self, tx_json: str, seal_sk: bytes) -> str:
        """Seal an unsigned/unsealed transaction with the seal signer's secret."""
        ...

    def bor_encode_transaction(self, transaction_json: str) -> str:
        """BOR-encode a sealed transaction. Returns base64."""
        ...
