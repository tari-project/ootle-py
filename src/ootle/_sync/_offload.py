"""Offload a synchronous, blocking call (sync mirror — direct invocation).

Sync counterpart of :mod:`ootle._async._offload`. The async form awaits
:func:`asyncio.to_thread` so the event loop stays free; the synchronous
client has no event loop to protect, so :func:`offload` simply calls
``fn``. Both forms are hand-maintained — see ``scripts/unasync.py``'s
``HANDMAINTAINED_FILES`` — because the divergence cannot be expressed by
the ``unasync`` token-rewriter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def offload[T](fn: Callable[[], T]) -> T:
    """Call ``fn`` and return its result.

    ``fn`` is a zero-argument callable — the call site binds the arguments
    in a ``lambda`` (or :func:`functools.partial`) so this stays a thin
    pass-through that mirrors the async form's signature.
    """
    return fn()
