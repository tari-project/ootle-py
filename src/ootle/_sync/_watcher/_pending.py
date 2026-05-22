"""``PendingTransaction`` — handle for a submitted transaction (sync).

Hand-written sync counterpart of
:class:`ootle._async._watcher._pending.AsyncPendingTransaction`. See that
module's docstring; the differences are the blocking call shapes
(``Future.result(timeout)`` instead of ``asyncio.wait_for`` and
``time.sleep`` instead of ``asyncio.sleep``) and cancellation handling — a
blocking ``Future.result()`` only raises ``CancelledError`` when the watcher
cancels the future, so there is no caller-task cancellation to distinguish.
"""

from __future__ import annotations

import dataclasses
import logging
import time
from concurrent.futures import CancelledError as FutureCancelledError
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from ootle._types.outcome import TransactionOutcome
from ootle.errors import IndexerClientError, TransactionRejectedError, TransactionTimeoutError

if TYPE_CHECKING:
    from ootle._sync._transport import IndexerTransport
    from ootle._sync._watcher._actor import TransactionWatcher
    from ootle._types.receipt import TransactionReceipt
    from ootle._types.transaction import TransactionId

logger = logging.getLogger(__name__)

_COMMIT_TAG = "Commit"
_REST_POLL_INTERVAL = 1.0
"""Seconds between REST polls when the SSE watcher is unavailable."""
_RECEIPT_POLL_INTERVAL = 0.5
"""Seconds between receipt polls while the indexer persists the result."""
_RECEIPT_WAIT_TIMEOUT = 10.0
"""Total seconds to wait for the receipt after finalisation before giving up."""


@dataclass(frozen=True, slots=True)
class PendingTransaction:
    """Handle for a submitted transaction; call :meth:`watch` to finalise."""

    tx_id: TransactionId
    _transport: IndexerTransport
    _watcher: TransactionWatcher | None = field(default=None)
    _timeout: float = field(default=60.0)

    def with_timeout(self, timeout: float) -> Self:
        """Return a copy with a new finalisation deadline (seconds)."""
        return dataclasses.replace(self, _timeout=timeout)

    def watch(self) -> TransactionOutcome:
        """Wait for the transaction to finalise. Raises on rejection / timeout.

        Returns :meth:`TransactionOutcome.commit` /
        :meth:`~TransactionOutcome.only_fee_commit`. ``Commit`` is taken
        from the SSE event directly; any other finalisation tag is confirmed
        with a single REST result query. If the SSE wait yields nothing —
        deadline reached, or the watcher stopped before finalisation — fall
        back to polling REST for whatever time remains, matching the
        resilience of the no-watcher path.

        Raises:
            TransactionRejectedError: Consensus rejected the transaction.
            TransactionTimeoutError: Finalisation was not observed in time.
        """
        if self._watcher is None:
            return self._poll_until_finalized(self._timeout)
        deadline = time.monotonic() + self._timeout
        tag = self._await_sse(self._watcher)
        if tag == _COMMIT_TAG:
            return TransactionOutcome.commit()
        if tag is not None:
            return self._resolve_via_rest()
        return self._poll_until_finalized(max(deadline - time.monotonic(), 0.0))

    def get_receipt(self, *, timeout: float | None = None) -> TransactionReceipt:
        """Fetch the full transaction receipt, polling until it is available.

        After :meth:`watch` observes finalisation over SSE, the indexer may not
        have persisted the receipt at ``GET /transaction-receipts/{id}`` yet, so
        a single fetch can race and 404. Poll until the receipt resolves or
        *timeout* seconds elapse.

        Args:
            timeout: Seconds to wait for the receipt. Defaults to
                ``_RECEIPT_WAIT_TIMEOUT``; pass ``0`` to attempt exactly once.

        Raises:
            IndexerClientError: The receipt did not become available in time.
        """
        deadline = time.monotonic() + (_RECEIPT_WAIT_TIMEOUT if timeout is None else timeout)
        while True:
            receipt = self._transport.get_transaction_receipt(self.tx_id)
            if receipt is not None:
                return receipt
            if time.monotonic() >= deadline:
                msg = f"transaction receipt for {self.tx_id} not found"
                raise IndexerClientError(msg, status=404, body="", url=self._transport.url)
            time.sleep(_RECEIPT_POLL_INTERVAL)

    def _await_sse(self, watcher: TransactionWatcher) -> str | None:
        future = watcher.register(self.tx_id)
        try:
            # concurrent.futures.TimeoutError is an alias of builtin TimeoutError (3.11+).
            return future.result(self._timeout)
        except TimeoutError:
            logger.warning("transaction %s: SSE deadline reached, polling result", self.tx_id)
            return None
        except FutureCancelledError:
            # The watcher cancelled the registered future on shutdown; fall back to REST.
            logger.warning("transaction %s: SSE watcher stopped, polling result", self.tx_id)
            return None
        finally:
            watcher.unregister(self.tx_id)

    def _resolve_via_rest(self) -> TransactionOutcome:
        is_finalized, outcome = self._transport.get_transaction_result(self.tx_id)
        if not is_finalized or outcome is None:
            msg = f"transaction {self.tx_id} did not finalise within {self._timeout}s"
            raise TransactionTimeoutError(msg, tx_id=self.tx_id)
        return self._classify(outcome)

    def _poll_until_finalized(self, timeout: float) -> TransactionOutcome:
        deadline = time.monotonic() + timeout
        while True:
            is_finalized, outcome = self._transport.get_transaction_result(self.tx_id)
            if is_finalized and outcome is not None:
                return self._classify(outcome)
            if time.monotonic() >= deadline:
                msg = f"transaction {self.tx_id} did not finalise within {self._timeout}s"
                raise TransactionTimeoutError(msg, tx_id=self.tx_id)
            time.sleep(_REST_POLL_INTERVAL)

    def _classify(self, outcome: TransactionOutcome) -> TransactionOutcome:
        if outcome.is_reject:
            msg = f"transaction {self.tx_id} rejected: {outcome.reason}"
            raise TransactionRejectedError(
                msg,
                tx_id=self.tx_id,
                reason=outcome.reason or "",
                reject_reason=outcome.reject_reason,
            )
        return outcome
