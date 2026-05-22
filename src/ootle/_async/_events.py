"""``watch_events`` — SSE-based template event subscriber.

Streams template events from the indexer's
``GET /transactions/events/stream`` endpoint (the
``sse_transaction_events`` route in ``tari_indexer_client``).
Server-side filtering is applied via query parameters; client-side
filtering provides defence-in-depth for stale indexer versions that
ignore unknown query params.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from httpx_sse import aconnect_sse as _open_sse_stream

from ootle._types._json import parse_sse_event

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from ootle._async._transport import AsyncIndexerTransport
    from ootle._types.address import TemplateAddress
    from ootle._types.events import TransactionEvent
    from ootle._types.substate import SubstateId


async def watch_events(
    transport: AsyncIndexerTransport,
    *,
    topic: str | None = None,
    substate_id: SubstateId | None = None,
    template_address: TemplateAddress | None = None,
) -> AsyncIterator[TransactionEvent]:
    """Yield :class:`~ootle._types.events.TransactionEvent` from the SSE stream.

    Args:
        transport: The indexer transport to use.
        topic: Optional event topic filter (``"Template::EventName"``).
        substate_id: Optional substate id filter.
        template_address: Optional template address filter.

    Yields:
        Matching :class:`TransactionEvent` objects as they arrive.
    """
    params: dict[str, str] = {}
    if topic is not None:
        params["topic"] = topic
    if substate_id is not None:
        params["substate_id"] = substate_id.opaque
    if template_address is not None:
        params["template_address"] = str(template_address)

    url = f"{transport.url}/transactions/events/stream"
    async with _open_sse_stream(transport.client, "GET", url, params=params) as source:
        async for sse in source.aiter_sse():
            event = _parse_sse_event(sse_topic=sse.event, sse_id=sse.id, data=sse.data)
            if event is None:
                continue
            if _matches(
                event, topic=topic, substate_id=substate_id, template_address=template_address
            ):
                yield event


def _parse_sse_event(*, sse_topic: str, sse_id: str, data: str) -> TransactionEvent | None:
    """Parse a raw SSE event into a :class:`TransactionEvent`, or ``None`` on error.

    The indexer transmits the event topic via the SSE ``event:`` line and a
    monotonic event id via the SSE ``id:`` line; the JSON body carries
    ``{transaction_id, event: {substate_id, template_address, payload}}``.
    """
    try:
        raw: Any = json.loads(data)
        if not isinstance(raw, dict):
            return None
        return parse_sse_event(sse_topic, sse_id, cast("dict[str, Any]", raw))
    except (ValueError, TypeError, KeyError):
        return None


def _matches(
    event: TransactionEvent,
    *,
    topic: str | None,
    substate_id: SubstateId | None,
    template_address: TemplateAddress | None,
) -> bool:
    """Return ``True`` if *event* satisfies all non-``None`` filter fields."""
    if topic is not None and event.topic != topic:
        return False
    if substate_id is not None and event.substate_id != substate_id:
        return False
    return template_address is None or event.template_address == template_address
