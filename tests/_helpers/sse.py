"""Fake SSE plumbing for testing the watchers without a live indexer.

Patches :func:`httpx_sse.aconnect_sse` (and ``connect_sse`` for the sync
mirror) to yield a fixed list of ``ServerSentEvent``-shaped objects. With
``keep_open=True`` the source stays open after the canned events — the
transaction-watcher actor expects a long-lived stream, so it would loop
reconnecting otherwise. The async source unblocks on task cancellation;
the sync source unblocks when ``source.response.close()`` is called.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator
    from collections.abc import Sequence as _Seq

_RawEvent = tuple[str, str] | tuple[str, str, str]
"""Either ``(event, data)`` (id defaults to empty) or ``(event, id, data)``."""


def _unpack(raw: _RawEvent) -> tuple[str, str, str]:
    if len(raw) == 2:
        ev_type, data = raw
        return ev_type, "", data
    return raw


class _FakeEvent:
    """Stand-in for :class:`httpx_sse.ServerSentEvent` (``.event`` / ``.id`` / ``.data``)."""

    __slots__ = ("data", "event", "id")

    def __init__(self, event: str, data: str, *, id: str = "") -> None:
        self.event = event
        self.id = id
        self.data = data


class _FakeResponse:
    """Stand-in for the ``httpx.Response`` behind an :class:`httpx_sse.EventSource`."""

    __slots__ = ("_stop",)

    def __init__(self, stop: threading.Event) -> None:
        self._stop = stop

    def close(self) -> None:
        self._stop.set()


class _FakeEventSource:
    """Stand-in for :class:`httpx_sse.EventSource`."""

    def __init__(self, events: _Seq[_RawEvent], *, keep_open: bool = False) -> None:
        self._events = [_unpack(e) for e in events]
        self._keep_open = keep_open
        self._stop = threading.Event()
        self.response = _FakeResponse(self._stop)

    async def aiter_sse(self) -> AsyncIterator[_FakeEvent]:
        for ev_type, ev_id, data in self._events:
            yield _FakeEvent(ev_type, data, id=ev_id)
        if self._keep_open:
            await asyncio.Event().wait()  # released by task cancellation

    def iter_sse(self) -> Iterator[_FakeEvent]:
        for ev_type, ev_id, data in self._events:
            yield _FakeEvent(ev_type, data, id=ev_id)
        if self._keep_open:
            self._stop.wait()  # released by `response.close()`


@asynccontextmanager
async def fake_aconnect_sse(events: _Seq[_RawEvent], *, keep_open: bool = False):
    """Async context manager producing a fake SSE source from ``events``."""
    yield _FakeEventSource(events, keep_open=keep_open)


@contextmanager
def fake_connect_sse(events: _Seq[_RawEvent], *, keep_open: bool = False):
    """Sync context manager producing a fake SSE source from ``events``."""
    yield _FakeEventSource(events, keep_open=keep_open)
