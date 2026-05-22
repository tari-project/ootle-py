"""Exception taxonomy for ``ootle``.

Every exception raised by this package inherits from :class:`OotleError`.
Subclasses carry structured attributes — callers should access fields,
not parse messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from ootle._types.reject_reason import RejectReason
    from ootle._types.transaction import TransactionId


class OotleError(Exception):
    """Base class for every exception raised by ``ootle``."""


class IndexerClientError(OotleError):
    """Raised when the indexer transport fails or returns a 4xx/5xx.

    Attributes:
        status: HTTP status code if the request reached the indexer.
            ``None`` if the failure was at the connection layer.
        body: Raw response body (or empty if not available).
        url: The full URL that was requested.
    """

    def __init__(self, message: str, *, status: int | None, body: str, url: str) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.url = url

    @override
    def __str__(self) -> str:
        return f"{super().__str__()} (status={self.status}, url={self.url})"


class TransactionRejectedError(OotleError):
    """Raised when consensus rejects a transaction.

    Attributes:
        tx_id: The rejected transaction's identifier.
        reason: Human-readable reason (Rust ``Display`` form when available).
        reject_reason: Structured engine rejection reason if available,
            else ``None`` (the indexer fell back to a free-form
            ``abort_details`` string).
    """

    def __init__(
        self,
        message: str,
        *,
        tx_id: TransactionId,
        reason: str,
        reject_reason: RejectReason | None = None,
    ) -> None:
        super().__init__(message)
        self.tx_id = tx_id
        self.reason = reason
        self.reject_reason = reject_reason

    @override
    def __str__(self) -> str:
        return f"{super().__str__()} (tx_id={self.tx_id}, reason={self.reason})"


class TransactionTimeoutError(OotleError):
    """Raised when both the SSE watch and fallback poll timed out.

    Attributes:
        tx_id: The transaction whose finalisation could not be observed.
    """

    def __init__(self, message: str, *, tx_id: TransactionId) -> None:
        super().__init__(message)
        self.tx_id = tx_id

    @override
    def __str__(self) -> str:
        return f"{super().__str__()} (tx_id={self.tx_id})"


class WalletError(OotleError):
    """Raised by :class:`ootle.OotleWallet` operations.

    Subclasses (``KeyProviderNotFoundError``, ``DefaultSignerNotSetError``)
    are exposed as attributes of this class so that callers can write
    ``except WalletError.KeyProviderNotFoundError`` per the v1 docs.
    """

    KeyProviderNotFoundError: type[KeyProviderNotFoundError]
    DefaultSignerNotSetError: type[DefaultSignerNotSetError]


class KeyProviderNotFoundError(WalletError):
    """The wallet has no signer registered for the given address."""

    def __init__(self, message: str, *, address: object) -> None:
        super().__init__(message)
        self.address = address


class DefaultSignerNotSetError(WalletError):
    """The wallet has no default signer to seal with."""


WalletError.KeyProviderNotFoundError = KeyProviderNotFoundError
WalletError.DefaultSignerNotSetError = DefaultSignerNotSetError


class SignerError(OotleError):
    """Raised when a :class:`ootle.Signer` fails to sign or seal."""


class CryptoBridgeError(OotleError):
    """Raised when the WASM crypto bridge fails.

    Attributes:
        context: Short label identifying *which* bridge call failed
            (e.g. ``"VERSION parse"`` or ``"schnorr_sign"``).

    The original Python exception (if any) is attached via
    :pep:`3134` chaining — read it through ``err.__cause__``.
    """

    def __init__(self, message: str, *, context: str | None = None) -> None:
        super().__init__(message)
        self.context = context

    @override
    def __str__(self) -> str:
        base = super().__str__()
        return f"[{self.context}] {base}" if self.context else base


class InvalidArgumentError(OotleError):
    """Raised when builder or helper inputs fail Python-side validation."""
