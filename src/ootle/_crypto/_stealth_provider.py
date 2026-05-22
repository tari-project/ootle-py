"""``StealthCryptoProvider`` Protocol — sync seam for stealth crypto.

See :mod:`ootle._crypto._provider` for the rationale behind splitting
the base ``CryptoProvider`` and this stealth surface. Both Protocols are
synchronous (the WASM work behind them is synchronous) and both are
satisfied natively by :class:`ootle._crypto.WasmCryptoProvider`.

``StealthCryptoProvider`` and its :class:`SyncStealthCryptoProvider`
mirror are now byte-for-byte identical; the pair is retained only so the
``unasync`` substitution table keeps a stable name to rewrite to in the
generated ``_sync/stealth/`` tree.

Method signatures mirror the Rust upstream:

- ``generate_outputs_statement`` ↔ ``StealthOutputStatementFactory``
  (``crates/wallet/ootle-rs/src/stealth/traits.rs``).
- ``unblind_output`` ↔ ``InputDecryptor::decrypt_input_data`` (same file).
- ``stealth_dh_secret`` ↔ ``tari_ootle_wallet_crypto::kdfs::owner_stealth_dh_secret``.
- ``validate_transfer`` ↔ ``tari_ootle_common_types::engine_types::stealth::validate_transfer``.
- ``generate_balance_proof_signature`` and ``aggregate_input_masks`` mirror
  the vendored ``ootle-wasm`` stealth primitives.

All methods take/return dataclasses from :mod:`ootle._types.stealth` —
never raw dicts. JSON marshalling lives inside the implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

# Re-exported so consumers (and the unasync-generated sync tree) keep importing
# the sync mirror from this module; it lives in a sibling to respect the
# 200-line ceiling. No runtime cycle: the sibling only imports back under
# TYPE_CHECKING.
from ._stealth_provider_sync import SyncStealthCryptoProvider

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._types.stealth import (
        DecryptedData,
        Mask,
        Output,
        StealthOutputsStatement,
        StealthTransferStatement,
    )


@dataclass(frozen=True, slots=True)
class StealthOutputsStatementResult:
    """Result of :meth:`StealthCryptoProvider.generate_outputs_statement`.

    Mirrors Rust's ``(StealthOutputsStatement, RistrettoSecretKey)``
    tuple — the aggregated statement plus the 32-byte output mask the
    sender must keep to later spend the change.
    """

    statement: StealthOutputsStatement
    output_mask: Mask


class StealthCryptoProvider(Protocol):
    """Synchronous seam for stealth-specific primitives.

    The implementation routes to the vendored ``ootle-wasm`` stealth
    exports (:class:`ootle._crypto.WasmCryptoProvider`). Every method is a
    plain ``def`` — the WASM work behind it is synchronous behind a lock.
    The ``_async/`` callers offload each call onto a worker thread (see
    :func:`ootle._async._offload.offload`) so the event loop is not
    blocked; the generated ``_sync/stealth/`` tree calls directly through
    the :class:`SyncStealthCryptoProvider` mirror that ``unasync``
    substitutes in.
    """

    def generate_outputs_statement(
        self,
        specs: Sequence[Output],
        revealed_output_amount: int,
    ) -> StealthOutputsStatementResult:
        """Generate the output half of a stealth transfer.

        Mirrors Rust ``StealthOutputStatementFactory::generate_outputs_statement``.
        """
        ...

    def generate_balance_proof_signature(
        self,
        input_mask: Mask,
        output_mask: Mask,
        inputs_statement_json: str,
        outputs_statement_json: str,
    ) -> bytes:
        """Sign the ``inputs == outputs`` balance proof. Returns 64 bytes."""
        ...

    def unblind_output(
        self,
        commitment: bytes,
        output_body_json: str,
        view_secret: bytes,
        skip_memo: bool,
    ) -> DecryptedData:
        """Decrypt an inbound stealth UTXO using the view secret."""
        ...

    def aggregate_input_masks(self, masks: Sequence[Mask]) -> Mask:
        """Sum the input commitment masks into one aggregated mask.

        Mirrors Rust ``aggregate_input_masks`` (a Ristretto scalar sum):
        an empty sequence yields the zero scalar, a single mask is
        returned unchanged. The result feeds ``input_mask`` of
        :meth:`generate_balance_proof_signature`.
        """
        ...

    def stealth_dh_secret(
        self,
        network_byte: int,
        owner_secret: bytes,
        public_nonce: bytes,
    ) -> bytes:
        """Diffie-Hellman: derive the 32-byte shared stealth secret."""
        ...

    def validate_transfer(self, transfer_statement: StealthTransferStatement) -> None:
        """Pre-flight sanity check; raises on an inconsistent transfer envelope."""
        ...


__all__ = [
    "StealthCryptoProvider",
    "StealthOutputsStatementResult",
    "SyncStealthCryptoProvider",
]
