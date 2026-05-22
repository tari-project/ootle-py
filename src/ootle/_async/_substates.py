"""Substate fetch helpers delegated from ``AsyncOotleClient``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle.errors import IndexerClientError

from ._transport import HTTP_NOT_FOUND

if TYPE_CHECKING:
    from ootle._async._transport import AsyncIndexerTransport
    from ootle._types.substate import Substate, SubstateId


async def get_substate(transport: AsyncIndexerTransport, id: SubstateId) -> Substate:
    """Return the substate; raise :class:`IndexerClientError` on 404."""
    substate = await transport.fetch_substate(id)
    if substate is not None:
        return substate
    url = f"{transport.url}/substates/{id.opaque}"
    raise IndexerClientError(
        f"substate not found: {id.opaque}", status=HTTP_NOT_FOUND, body="", url=url
    )
