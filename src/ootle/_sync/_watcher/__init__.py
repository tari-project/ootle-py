"""Per-transaction watcher: the multiplexed SSE actor + the pending handle (sync).

Hand-written sync counterpart of :mod:`ootle._async._watcher`; this
package is excluded from the ``unasync`` pipeline.
"""

from __future__ import annotations

from ootle._sync._watcher._actor import TransactionWatcher
from ootle._sync._watcher._pending import PendingTransaction

__all__ = ["PendingTransaction", "TransactionWatcher"]
