"""``TransactionEvent`` and ``TransactionEventFilter``.

Template-emitted events as the indexer streams them over SSE. The
filter object is consumed by ``client.watch_events(...)`` in M6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ootle._types.address import TemplateAddress
    from ootle._types.substate import SubstateId
    from ootle._types.transaction import TransactionId


@dataclass(frozen=True, slots=True)
class TransactionEvent:
    """A single template-emitted event.

    Attributes:
        topic: Event topic, typically ``"<Template>::<EventName>"``. The
            indexer transmits this on the SSE ``event:`` line.
        payload: Decoded event body as a JSON-shaped mapping.
        template_address: The template that emitted the event.
        substate_id: The substate (component / vault / resource) that
            emitted the event, if attributable.
        id: Monotonic event id assigned by the indexer (SSE ``id:`` line);
            ``None`` for synthetic events that never traversed the indexer.
        transaction_id: Transaction that produced the event; ``None`` for
            events that don't carry one (e.g. older indexers).
    """

    topic: str
    payload: dict[str, Any] = field(default_factory=dict[str, Any])
    template_address: TemplateAddress | None = None
    substate_id: SubstateId | None = None
    id: int | None = None
    transaction_id: TransactionId | None = None


@dataclass(frozen=True, slots=True)
class TransactionEventFilter:
    """Subscription filter passed to ``client.watch_events(...)``.

    Each ``None`` field is treated as a wildcard. An all-``None`` filter
    subscribes to every event.
    """

    topic: str | None = None
    substate_id: SubstateId | None = None
    template_address: TemplateAddress | None = None
