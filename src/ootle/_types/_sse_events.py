"""Parsing for the indexer's ``TransactionFinalized`` SSE event payload.

Shared (pure-sync) helper used by both the async and the sync transaction
watchers (:mod:`ootle._async._watcher`, :mod:`ootle._sync._watcher`). The
``ootle-wasm`` bridge owns Borsh; an SSE event payload is plain JSON.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from ootle._types.transaction import TransactionId

FINALIZED_EVENT_TYPE = "TransactionFinalized"
"""The SSE ``event:`` type the indexer emits when a transaction finalises."""


def parse_finalized_event(data: str) -> tuple[TransactionId, str | None] | None:
    """Extract ``(transaction_id, outcome_tag)`` from a ``TransactionFinalized`` payload.

    Returns ``None`` if the payload is malformed or carries no transaction
    id. ``outcome_tag`` is ``"Commit"`` / ``"FeeIntentCommit"`` when the
    event states it plainly, or ``None`` for any other shape — the caller
    then resolves the real outcome with a REST result query.
    """
    try:
        raw: Any = json.loads(data)
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    payload = cast("dict[str, Any]", raw)
    tx_id = payload.get("transaction_id")
    if not isinstance(tx_id, str):
        return None
    return cast("TransactionId", tx_id), _outcome_tag(payload.get("outcome"))


def _outcome_tag(outcome: object) -> str | None:
    if isinstance(outcome, str):
        return outcome
    # Older indexers emit `{"Commit": null}` (externally-tagged) instead of
    # the bare variant name; both reduce to the single key.
    if isinstance(outcome, dict):
        keys = list(cast("dict[str, Any]", outcome))
        if len(keys) == 1:
            return keys[0]
    return None
