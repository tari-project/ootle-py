"""``TransactionOutcome`` — committed, fee-only-committed, or rejected.

The Rust upstream uses an ``enum`` with three variants. Python uses a
single dataclass with a ``kind`` discriminator plus three classmethod
constructors that enforce the ``reason`` invariant: ``commit`` carries
no reason; the other two require one.

When the outcome is a rejection (full or fee-only), ``reject_reason``
holds the structured engine variant — see
:mod:`ootle._types.reject_reason`. It is ``None`` only when the
indexer falls back to a free-form ``abort_details`` string with no
structured form available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Self

if TYPE_CHECKING:
    from ootle._types.reject_reason import RejectReason

OutcomeKind = Literal["commit", "only_fee_commit", "reject"]


@dataclass(frozen=True, slots=True)
class TransactionOutcome:
    """The on-chain outcome of a finalised transaction."""

    kind: OutcomeKind
    reason: str | None = None
    reject_reason: RejectReason | None = None

    @classmethod
    def commit(cls) -> Self:
        """The transaction was fully committed."""
        return cls(kind="commit", reason=None)

    @classmethod
    def only_fee_commit(cls, reason: str, reject_reason: RejectReason | None = None) -> Self:
        """The transaction failed but its fee instructions committed."""
        return cls(kind="only_fee_commit", reason=reason, reject_reason=reject_reason)

    @classmethod
    def reject(cls, reason: str, reject_reason: RejectReason | None = None) -> Self:
        """The transaction was rejected without any state changes."""
        return cls(kind="reject", reason=reason, reject_reason=reject_reason)

    @property
    def is_commit(self) -> bool:
        return self.kind == "commit"

    @property
    def is_only_fee_commit(self) -> bool:
        return self.kind == "only_fee_commit"

    @property
    def is_reject(self) -> bool:
        return self.kind == "reject"
