"""End-to-end event-watching flow against a real LocalNet indexer.

Gated on the ``OOTLE_INDEXER_URL`` env var. Run with::

    OOTLE_INDEXER_URL=http://localhost:12500 \\
        uv run pytest -m integration tests/_async/integration/test_event_watching_e2e.py
"""

from __future__ import annotations

import pytest

from ootle import OotleClient
from ootle._types.events import TransactionEventFilter

pytestmark = pytest.mark.integration


def test_watch_events_returns_async_iterable(indexer_url: str) -> None:
    """Verify ``watch_events`` returns an object that can be iterated asynchronously."""
    with OotleClient.connect(indexer_url) as client:
        stream = client.watch_events()
        assert hasattr(stream, "__iter__")
        assert hasattr(stream, "__next__")


def test_watch_events_with_filter_returns_async_iterable(indexer_url: str) -> None:
    """Verify filtered ``watch_events`` returns an async iterable."""
    with OotleClient.connect(indexer_url) as client:
        f = TransactionEventFilter(topic="Counter::Incremented")
        stream = client.watch_events(f)
        assert hasattr(stream, "__iter__")
        assert hasattr(stream, "__next__")
