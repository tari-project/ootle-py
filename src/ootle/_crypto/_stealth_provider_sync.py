"""``SyncStealthCryptoProvider`` — sync mirror of the stealth Protocol.

Split from :mod:`ootle._crypto._stealth_provider` to keep both files
under the 200-line ceiling. Re-exported from there, so consumers still
``from ootle._crypto._stealth_provider import SyncStealthCryptoProvider``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._crypto._stealth_provider import StealthOutputsStatementResult
    from ootle._types.stealth import (
        DecryptedData,
        Mask,
        Output,
        StealthTransferStatement,
    )


class SyncStealthCryptoProvider(Protocol):
    """Mirror of :class:`~ootle._crypto._stealth_provider.StealthCryptoProvider`.

    Identical shape — both Protocols are now synchronous. Consumed by the
    generated ``_sync/stealth/`` tree; the ``unasync`` substitution table
    rewrites the Protocol reference in the sync mirror to this name.
    """

    def generate_outputs_statement(
        self,
        specs: Sequence[Output],
        revealed_output_amount: int,
    ) -> StealthOutputsStatementResult:
        """Sync counterpart of :meth:`StealthCryptoProvider.generate_outputs_statement`."""
        ...

    def generate_balance_proof_signature(
        self,
        input_mask: Mask,
        output_mask: Mask,
        inputs_statement_json: str,
        outputs_statement_json: str,
    ) -> bytes:
        """Sync counterpart of :meth:`StealthCryptoProvider.generate_balance_proof_signature`."""
        ...

    def unblind_output(
        self,
        commitment: bytes,
        output_body_json: str,
        view_secret: bytes,
        skip_memo: bool,
    ) -> DecryptedData:
        """Sync counterpart of :meth:`StealthCryptoProvider.unblind_output`."""
        ...

    def aggregate_input_masks(self, masks: Sequence[Mask]) -> Mask:
        """Sync counterpart of :meth:`StealthCryptoProvider.aggregate_input_masks`."""
        ...

    def stealth_dh_secret(
        self,
        network_byte: int,
        owner_secret: bytes,
        public_nonce: bytes,
    ) -> bytes:
        """Sync counterpart of :meth:`StealthCryptoProvider.stealth_dh_secret`."""
        ...

    def validate_transfer(self, transfer_statement: StealthTransferStatement) -> None:
        """Sync counterpart of :meth:`StealthCryptoProvider.validate_transfer`."""
        ...
