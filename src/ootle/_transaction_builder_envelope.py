"""``EnvelopeMixin`` — the transaction-envelope knobs of :class:`TransactionBuilder`.

Split out of ``_transaction_builder.py`` to keep that module under the
200-line limit. These setters touch only ``UnsignedTransactionV1``'s
envelope fields (validity window, dry-run flag, nonce) — never the
instruction or fee blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from ootle._types._tx_body import UnsignedTransactionV1Body


class EnvelopeMixin:
    """Envelope-field setters shared into :class:`TransactionBuilder`."""

    __slots__ = ()

    _body: UnsignedTransactionV1Body

    def with_dry_run(self, dry_run: bool) -> Self:
        """Set the ``dry_run`` flag on the unsigned transaction."""
        self._body.dry_run = dry_run
        return self

    def with_min_epoch(self, epoch: int | None) -> Self:
        """Set the minimum epoch the transaction is valid in."""
        self._body.min_epoch = epoch
        return self

    def with_max_epoch(self, epoch: int) -> Self:
        """Set the last epoch the transaction may be sequenced in.

        Mandatory on the wire: every transaction carries a bounded validity
        window. Async builders default it at ``prepare()`` time from the live
        network epoch; a builder used standalone must set it explicitly.
        """
        self._body.max_epoch = epoch
        return self

    @property
    def max_epoch(self) -> int | None:
        """The configured ``max_epoch``, or ``None`` while still unset."""
        return self._body.max_epoch

    def with_nonce(self, nonce: int) -> Self:
        """Set the nonce distinguishing otherwise-identical transaction bodies.

        The transaction id excludes the seal signature, so two identical bodies
        sealed by the same key are the *same* transaction. Stamp a distinct
        nonce per intent when each submission must execute independently.
        """
        self._body.nonce = nonce
        return self
