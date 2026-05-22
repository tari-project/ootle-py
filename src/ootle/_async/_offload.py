"""Offload a synchronous, blocking call onto a worker thread.

The stealth crypto surface (:class:`~ootle._crypto._stealth_provider.\
StealthCryptoProvider`) is synchronous — it drives the vendored WASM blob
behind a lock with no I/O of its own. The ``_async/`` callers must not run
that compute inline or it blocks the event loop for the full WASM work, so
they wrap each call in :func:`offload`.

This module is hand-maintained for *both* the ``_async`` and ``_sync``
trees (it is listed in ``scripts/unasync.py``'s ``HANDMAINTAINED_FILES``):
the async form awaits :func:`asyncio.to_thread`, the sync form invokes the
callable directly — a divergence the token-rewriter cannot express.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


async def offload[T](fn: Callable[[], T]) -> T:
    """Run ``fn`` on a worker thread and return its result.

    ``fn`` is a zero-argument callable — wrap the real call in a
    ``lambda`` (or :func:`functools.partial`) at the call site so the
    arguments are bound here, not threaded through.
    """
    return await asyncio.to_thread(fn)
