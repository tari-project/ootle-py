"""``AsyncTransactionWatcher`` — multiplexed ``/events`` SSE subscription.

One long-lived ``GET /events`` stream per client, opened lazily *before*
the first transaction is submitted and fanned out to per-transaction
futures keyed by ``transaction_id``. Mirrors the actor in Rust's
``provider/tx_watcher.rs`` minus the pause/reap bookkeeping (deferred to
v2).

Hand-maintained for *both* the async and the sync tree: the async/sync
forms diverge structurally (``asyncio`` task + :class:`asyncio.Future`
vs. a worker thread + :class:`concurrent.futures.Future`), so this
package is excluded from the ``unasync`` pipeline — see
``scripts/unasync.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from httpx_sse import aconnect_sse as _open_sse_stream

from ootle._types._sse_events import FINALIZED_EVENT_TYPE, parse_finalized_event

if TYPE_CHECKING:
    import httpx
    from httpx_sse import ServerSentEvent

    from ootle._types.transaction import TransactionId

logger = logging.getLogger(__name__)

_EVENTS_PATH = "/events"
_RECONNECT_DELAY = 1.0
"""Seconds to wait before re-subscribing after the ``/events`` stream drops."""


class AsyncTransactionWatcher:
    """Background subscriber that resolves per-transaction finalisation futures.

    Created and started by :meth:`AsyncIndexerTransport.transaction_watcher`;
    callers interact with it only indirectly via
    :class:`~ootle._async._watcher._pending.AsyncPendingTransaction`.
    """

    __slots__ = (
        "_client",
        "_connect_error",
        "_connected",
        "_events_url",
        "_registry",
        "_running",
        "_task",
    )

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._events_url = f"{base_url.rstrip('/')}{_EVENTS_PATH}"
        self._registry: dict[TransactionId, asyncio.Future[str | None]] = {}
        self._task: asyncio.Task[None] | None = None
        self._connected: asyncio.Event = asyncio.Event()
        self._connect_error: BaseException | None = None
        self._running = False

    async def start(self) -> None:
        """Subscribe to ``/events`` and block until the stream is live.

        Idempotent. Raises whatever the first subscription attempt raised
        if it failed — the caller is expected to fall back to REST polling.
        """
        if self._task is not None:
            return
        self._connected = asyncio.Event()
        self._connect_error = None
        self._running = True
        self._task = asyncio.create_task(self._run(), name="ootle-tx-watcher")
        await self._connected.wait()
        if self._connect_error is not None:
            error = self._connect_error
            await self.aclose()
            raise error

    def register(self, tx_id: TransactionId) -> asyncio.Future[str | None]:
        """Return a future resolved with the ``outcome`` tag when *tx_id* finalises."""
        existing = self._registry.get(tx_id)
        if existing is not None and not existing.done():
            return existing
        future: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        self._registry[tx_id] = future
        return future

    def unregister(self, tx_id: TransactionId) -> None:
        """Drop the registration for *tx_id* (the caller stopped waiting)."""
        self._registry.pop(tx_id, None)

    async def aclose(self) -> None:
        """Stop the subscriber and settle any outstanding futures."""
        self._running = False
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        first_attempt = True
        try:
            while self._running:
                try:
                    async with _open_sse_stream(self._client, "GET", self._events_url) as source:
                        first_attempt = False
                        self._connected.set()
                        logger.debug("transaction watcher: subscribed to /events")
                        async for sse in source.aiter_sse():
                            self._dispatch(sse)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # keep the watcher alive across any /events fault
                    if first_attempt:
                        self._connect_error = exc
                        self._connected.set()
                        return
                    if not self._running:
                        break
                    logger.warning(
                        "transaction watcher: /events fault (%s); reconnecting in %ss",
                        exc,
                        _RECONNECT_DELAY,
                    )
                else:
                    if not self._running:
                        break
                    logger.info(
                        "transaction watcher: /events closed by indexer; reconnecting in %ss",
                        _RECONNECT_DELAY,
                    )
                await asyncio.sleep(_RECONNECT_DELAY)
        finally:
            self._settle_outstanding()

    def _dispatch(self, sse: ServerSentEvent) -> None:
        if sse.event != FINALIZED_EVENT_TYPE:
            return
        parsed = parse_finalized_event(sse.data)
        if parsed is None:
            return
        tx_id, outcome_tag = parsed
        future = self._registry.pop(tx_id, None)
        if future is None or future.done():
            return
        logger.debug("transaction watcher: %s finalised (outcome=%s)", tx_id, outcome_tag)
        future.set_result(outcome_tag)

    def _settle_outstanding(self) -> None:
        registry, self._registry = self._registry, {}
        for future in registry.values():
            if not future.done():
                future.cancel()
