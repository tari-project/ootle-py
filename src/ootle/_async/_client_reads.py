"""Read-side helpers wrapping ``_transport`` for :class:`AsyncOotleClient`.

Extracted into a sibling module to keep ``client.py`` under the 200-line
ceiling. Each function takes the transport explicitly so the helpers
are reusable from tests without an :class:`AsyncOotleClient` in hand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._substates import get_substate as _get_substate

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from ootle._async._transport import AsyncIndexerTransport
    from ootle._types.events import TransactionEvent, TransactionEventFilter
    from ootle._types.network import Network
    from ootle._types.substate import Substate, SubstateId


async def get_network_for_client(transport: AsyncIndexerTransport) -> Network:
    """Round-trip ``GET network`` and return the current network."""
    info = await transport.get_network_info()
    return info.network


async def get_epoch_for_client(transport: AsyncIndexerTransport) -> int:
    """Round-trip ``GET network`` and return the current epoch."""
    info = await transport.get_network_info()
    return info.epoch


async def get_substate_for_client(transport: AsyncIndexerTransport, id: SubstateId) -> Substate:
    """Return the substate; raise :class:`IndexerClientError` on 404."""
    return await _get_substate(transport, id)


async def fetch_substates_for_client(
    transport: AsyncIndexerTransport, ids: Sequence[SubstateId]
) -> dict[SubstateId, Substate]:
    """Batched substate fetch; chunked at 20 per HTTP call."""
    return await transport.fetch_substates(ids)


def watch_events_for_client(
    transport: AsyncIndexerTransport,
    filter: TransactionEventFilter | None,
) -> AsyncIterator[TransactionEvent]:
    """Stream matching template events from the indexer SSE channel."""
    from ootle._async._events import watch_events as _watch  # noqa: PLC0415
    from ootle._types.events import TransactionEventFilter  # noqa: PLC0415

    f = filter or TransactionEventFilter()
    return _watch(
        transport,
        topic=f.topic,
        substate_id=f.substate_id,
        template_address=f.template_address,
    )
