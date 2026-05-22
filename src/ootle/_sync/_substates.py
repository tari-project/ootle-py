"""Substate fetch helpers delegated from ``OotleClient``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle.errors import IndexerClientError

from ._transport import HTTP_NOT_FOUND

if TYPE_CHECKING:
    from ootle._sync._transport import IndexerTransport
    from ootle._types.substate import Substate, SubstateId


def get_substate(transport: IndexerTransport, id: SubstateId) -> Substate:
    """Return the substate; raise :class:`IndexerClientError` on 404."""
    substate = transport.fetch_substate(id)
    if substate is not None:
        return substate
    url = f"{transport.url}/substates/{id.opaque}"
    raise IndexerClientError(
        f"substate not found: {id.opaque}", status=HTTP_NOT_FOUND, body="", url=url
    )
