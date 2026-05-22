"""``TransactionReceipt`` — the full receipt the indexer returns.

The shape mirrors the Rust ``TransactionReceipt`` JSON. v1 spells out
the fields users access programmatically; ``diff_summary`` carries the
typed list of substates the transaction created or updated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ootle._types.amount import Amount
from ootle._types.diff_summary import DiffSummary

if TYPE_CHECKING:
    from ootle._types.events import TransactionEvent


@dataclass(frozen=True, slots=True)
class FeeReceipt:
    """Fee accounting reported by the network (mirrors engine ``FeeReceipt``)."""

    total_fee_payment: Amount
    total_fees_paid: Amount
    total_fee_overcharge: Amount
    cost_breakdown: dict[str, int] = field(default_factory=dict[str, int])

    @property
    def total_fees_charged(self) -> Amount:
        """Total fees charged — the engine-computed sum of :attr:`cost_breakdown`."""
        return Amount(sum(self.cost_breakdown.values()))


@dataclass(frozen=True, slots=True)
class TransactionReceipt:
    """The receipt returned by ``client.get_transaction_receipt(...)``.

    Attributes:
        epoch: Epoch in which the transaction was finalised.
        fee_receipt: Fee summary.
        events: Template-emitted events, in commit order.
        logs: Free-form log lines emitted by the engine.
        diff_summary: Substates this transaction created or updated.
            See :class:`~ootle._types.diff_summary.DiffSummary`.
    """

    epoch: int
    fee_receipt: FeeReceipt
    events: tuple[TransactionEvent, ...] = ()
    logs: tuple[str, ...] = ()
    diff_summary: DiffSummary = field(default_factory=DiffSummary)
