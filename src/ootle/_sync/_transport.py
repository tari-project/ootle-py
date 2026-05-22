"""``IndexerTransport`` — the HTTP boundary class.

Owns or borrows an :class:`httpx.Client` and exposes typed wrapper
methods for the v1 indexer REST endpoints. SSE handling is layered on
top in :mod:`ootle._async._watcher` (M4); per-endpoint M4 helpers live
in :mod:`ootle._async._endpoints`. Paths match ``tari_indexer_client``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import quote

import httpx

from ootle._sync._endpoints import (
    get_transaction_receipt,
    get_transaction_result,
    get_transaction_watcher,
    parse_json_object,
    submit_transaction,
    submit_transaction_dry_run,
)
from ootle._types._indexer_json import (
    parse_indexer_substate,
    parse_indexer_substates_map,
    parse_network_info,
)
from ootle.errors import IndexerClientError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType

    from ootle._sync._watcher import TransactionWatcher
    from ootle._types.network import NetworkInfo
    from ootle._types.outcome import TransactionOutcome
    from ootle._types.receipt import TransactionReceipt
    from ootle._types.substate import Substate, SubstateId
    from ootle._types.transaction import DryRunResult, TransactionId


logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_FETCH_CHUNK = 20
HTTP_NOT_FOUND = 404


class IndexerTransport:
    """The single seam to the indexer's HTTP REST API."""

    __slots__ = ("_client", "_owns_client", "_tx_watcher", "url")

    url: str
    _client: httpx.Client
    _owns_client: bool
    _tx_watcher: TransactionWatcher | None

    def __init__(
        self,
        url: str,
        *,
        http_client: httpx.Client | None = None,
        timeout: httpx.Timeout = _DEFAULT_TIMEOUT,
    ) -> None:
        self.url = url.rstrip("/")
        if http_client is None:
            self._client = httpx.Client(base_url=self.url, timeout=timeout)
            self._owns_client = True
        else:
            self._client = http_client
            self._owns_client = False
        self._tx_watcher = None
        logger.info("indexer transport connected: url=%s", self.url)

    def close(self) -> None:
        """Close the SSE watcher (if started) and the HTTP client (if owned)."""
        if self._tx_watcher is not None:
            self._tx_watcher.close()
            self._tx_watcher = None
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def get_network_info(self) -> NetworkInfo:
        """``GET network`` → :class:`NetworkInfo`."""
        resp = self._request("GET", "network")
        assert resp is not None  # noqa: S101 — `allow_404=False` guarantees non-None
        return parse_json_object(resp, parse_network_info)

    def fetch_substate(self, id: SubstateId) -> Substate | None:
        """``GET substates/{id}`` → :class:`Substate` or ``None`` on 404."""
        path = f"substates/{quote(id.opaque, safe='')}"
        resp = self._request("GET", path, allow_404=True)
        if resp is None:
            return None
        return parse_json_object(resp, lambda d: parse_indexer_substate(id, d))

    def fetch_substates(self, ids: Sequence[SubstateId]) -> dict[SubstateId, Substate]:
        """``POST substates/fetch`` chunked at 20 ids per call.

        Missing substates are simply absent from the returned dict; no
        exception is raised for a partial result.
        """
        result: dict[SubstateId, Substate] = {}
        for i in range(0, len(ids), _FETCH_CHUNK):
            chunk = ids[i : i + _FETCH_CHUNK]
            if not chunk:
                continue
            payload: dict[str, Any] = {
                "requests": [s.opaque for s in chunk],
                "cached_only": False,
            }
            resp = self._request("POST", "substates/fetch", json=payload)
            assert resp is not None  # noqa: S101 — `allow_404=False` guarantees non-None
            result.update(parse_json_object(resp, parse_indexer_substates_map))
        return result

    @property
    def client(self) -> httpx.Client:
        """Underlying httpx client (for SSE streaming + advanced use)."""
        return self._client

    def submit_transaction(self, envelope_b64: str) -> TransactionId:
        """``POST /transactions`` → :class:`TransactionId`."""
        return submit_transaction(self, envelope_b64)

    def submit_transaction_dry_run(self, envelope_b64: str) -> DryRunResult:
        """``POST /transactions/dry-run`` → :class:`DryRunResult`."""
        return submit_transaction_dry_run(self, envelope_b64)

    def get_transaction_result(
        self, tx_id: TransactionId
    ) -> tuple[bool, TransactionOutcome | None]:
        """``GET /transactions/{id}/result`` → ``(is_finalized, outcome | None)``."""
        return get_transaction_result(self, tx_id)

    def get_transaction_receipt(self, tx_id: TransactionId) -> TransactionReceipt | None:
        """``GET /transaction-receipts/{id}`` → :class:`TransactionReceipt` or ``None``."""
        return get_transaction_receipt(self, tx_id)

    def transaction_watcher(self) -> TransactionWatcher | None:
        """Lazily open (or return) the multiplexed ``/events`` SSE watcher, or ``None``."""
        return get_transaction_watcher(self)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        allow_404: bool = False,
    ) -> httpx.Response | None:
        """Send a request and map errors to :class:`IndexerClientError`.

        When ``allow_404`` is true, a 404 response yields ``None`` instead
        of raising. Any other 4xx/5xx, timeout, or network error raises.
        """
        full_url = f"{self.url}/{path.lstrip('/')}"
        relative = f"/{path.lstrip('/')}"
        logger.debug("indexer request: %s %s", method, full_url)
        try:
            resp = self._client.request(method, relative, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise IndexerClientError(
                f"indexer request timed out: {method} {path}", status=None, body="", url=full_url
            ) from exc
        except httpx.NetworkError as exc:
            raise IndexerClientError(
                f"indexer request failed: {method} {path}: {exc}",
                status=None,
                body="",
                url=full_url,
            ) from exc
        if allow_404 and resp.status_code == HTTP_NOT_FOUND:
            return None
        if resp.is_error:
            raise IndexerClientError(
                f"indexer returned HTTP {resp.status_code} for {method} {path}",
                status=resp.status_code,
                body=resp.text,
                url=str(resp.url),
            )
        return resp
