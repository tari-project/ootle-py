"""``DiffSummary`` — the substate-diff side of ``TransactionReceipt``.

Mirrors the Rust ``DiffSummary`` / ``UpSubstate`` structs in
``engine_types::transaction_receipt``. ``upped`` lists every substate
the transaction created or updated, in commit order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ootle._types.substate import SubstateId


@dataclass(frozen=True, slots=True)
class UpSubstate:
    """A single substate that was created or updated by a transaction.

    Attributes:
        substate_id: The substate identifier (prefixed string —
            ``component_…``, ``vault_…``, ``resource_…``, etc.).
        version: The post-transaction substate version.
        value_hash: Hex-encoded 32-byte hash of the substate value, as
            computed by the engine.
    """

    substate_id: SubstateId
    version: int
    value_hash: str


@dataclass(frozen=True, slots=True)
class DiffSummary:
    """The substate-diff payload of a ``TransactionReceipt``.

    ``upped`` is the canonical answer to "what substates did this
    transaction produce". For a freshly-deployed component, the new
    ``component_…`` address shows up here.
    """

    upped: tuple[UpSubstate, ...] = ()
