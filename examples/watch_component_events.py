"""Live component-event monitoring via SSE.

Python port of ``ootle-rs/examples/watch_component_events.rs``. Connects
to a LocalNet indexer (no wallet required — read-only), subscribes to
template events filtered by component ``substate_id`` (and optionally
event topic), and prints each event as it arrives. On stream error the
example sleeps 5 s and reconnects.

Usage::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
    OOTLE_COMPONENT_ADDRESS=component_<hex64> \\
    uv run python -m examples.watch_component_events

Optional ``OOTLE_EVENT_TOPIC=Counter::Incremented`` narrows the
subscription to a single topic.

Caveat: the Python ``TransactionEventFilter`` does not currently expose
``after_id``, so this example cannot resume from the last-seen event on
reconnect — events that arrive while the stream is down will be lost.
The :class:`~ootle.TransactionEvent` does carry ``event.id``, so adding
filter-side ``after_id`` is the only remaining gap to Rust-example
parity.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys

import httpx
from httpx_sse import SSEError

from ootle import AsyncOotleClient, SubstateId, TransactionEventFilter

from ._common import NETWORK, indexer_url

RECONNECT_DELAY_SECONDS = 5.0


def _read_env() -> tuple[str, str, str | None]:
    component = os.environ.get("OOTLE_COMPONENT_ADDRESS")
    if not component:
        sys.exit(
            "Set OOTLE_COMPONENT_ADDRESS=component_<hex64> to the component you "
            "want to watch (e.g. an account component or a deployed Counter)."
        )
    if not component.startswith("component_"):
        sys.exit(f"OOTLE_COMPONENT_ADDRESS must start with 'component_' (got {component!r}).")

    topic = os.environ.get("OOTLE_EVENT_TOPIC") or None
    return indexer_url(), component, topic


async def _stream_once(client: AsyncOotleClient, event_filter: TransactionEventFilter) -> None:
    async for event in client.watch_events(event_filter):
        ev_id = event.id if event.id is not None else "?"
        tx_id = event.transaction_id if event.transaction_id is not None else "?"
        print(f"[event id={ev_id}] tx={tx_id} topic={event.topic!r}")
        if event.payload:
            print(f"          payload={event.payload}")


async def main() -> None:
    url, component, topic = _read_env()
    event_filter = TransactionEventFilter(topic=topic, substate_id=SubstateId(component))

    print(f"Network: {NETWORK.name}, indexer: {url}")
    print(f"Watching component {component}" + (f" (topic={topic!r})" if topic else ""))

    async with AsyncOotleClient.connect(url) as client:
        while True:
            try:
                await _stream_once(client, event_filter)
                print("Stream ended cleanly, reconnecting...")
            except (SSEError, httpx.HTTPError, OSError) as exc:
                print(f"Stream error: {exc!r}")
            print(f"  reconnecting in {RECONNECT_DELAY_SECONDS:g}s...")
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
