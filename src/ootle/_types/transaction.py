"""Transaction wrappers and the ``TransactionRequest`` builder dataclass.

These are thin Python wrappers around WASM-produced JSON strings. The
typed names pin which layer owns the format and let pyright catch
shape mistakes that an opaque ``str`` would not.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NewType, Self, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ootle._types.amount import Amount
    from ootle._types.events import TransactionEvent
    from ootle._types.outcome import TransactionOutcome

TransactionId = NewType("TransactionId", str)
"""Opaque transaction identifier (hex-encoded hash)."""


@dataclass(frozen=True, slots=True)
class UnsignedTransaction:
    """A transaction whose instructions are finalised but unsigned.

    The ``json`` payload is the WASM-side representation. The
    ``tx_id_preview`` property hashes the body via the bridge — call
    sites that need it can resolve a :class:`CryptoProvider` themselves.
    """

    json: str

    @property
    def tx_id_preview(self) -> TransactionId:
        """Compute the transaction id without signing."""
        from ootle._crypto import load_default_provider  # noqa: PLC0415

        crypto = load_default_provider()
        digest = crypto.hash_unsigned_transaction(self.json, b"\x00" * 32)
        return TransactionId(digest.hex())


@dataclass(frozen=True, slots=True)
class UnsealedTransaction:
    """A transaction with all authorisations attached but no seal."""

    json: str


@dataclass(frozen=True, slots=True)
class Transaction:
    """A sealed transaction — ready to submit to the indexer."""

    json: str


@dataclass(frozen=True, slots=True)
class TransactionAuthorization:
    """A co-signer's authorisation — to be folded in at seal time."""

    json: str


@dataclass(frozen=True, slots=True)
class TransactionRequest:
    """Pythonic replacement for the Rust ``TransactionRequest<S>`` type-state.

    The runtime check happens later — :func:`OotleClient.seal_transaction`
    raises :class:`InvalidArgumentError` if ``transaction`` is ``None``.
    """

    transaction: UnsignedTransaction | None = None
    authorizations: tuple[TransactionAuthorization, ...] = ()

    def with_transaction(self, tx: UnsignedTransaction) -> Self:
        """Return a copy with ``tx`` attached."""
        return dataclasses.replace(self, transaction=tx)

    def add_authorization(self, auth: TransactionAuthorization) -> Self:
        """Return a copy with ``auth`` appended to the authorisation tuple."""
        return dataclasses.replace(self, authorizations=(*self.authorizations, auth))

    def with_authorizations(self, auths: Iterable[TransactionAuthorization]) -> Self:
        """Return a copy whose authorisation tuple is replaced by ``auths``."""
        return dataclasses.replace(self, authorizations=tuple(auths))


def _get(d: Any, key: str) -> Any:
    """Extract *key* from *d* if it is a dict; return ``None`` otherwise."""
    if not isinstance(d, dict):
        return None
    return cast("dict[str, Any]", d).get(key)


def _finalize_block(raw: dict[str, Any]) -> Any:
    """The ``finalize`` block (engine ``FinalizeResult``) of an ``ExecuteResult``.

    Falls back to *raw* itself only when ``finalize`` is absent, so callers
    tolerate a payload that is already the ``finalize`` block. A present but
    empty ``finalize: {}`` is preserved rather than conflated with *raw*.
    """
    block = _get(raw, "finalize")
    return block if block is not None else raw


@dataclass(frozen=True, slots=True)
class DryRunResult:
    """Result of ``client.send_dry_run(...)``.

    The indexer returns the engine's ``ExecuteResult`` payload — the same
    ``finalize`` block a finalised transaction carries, minus the
    consensus decision — under :attr:`raw`, plus the transaction id the
    indexer assigns even for dry-runs.

    Use :attr:`estimated_fee`, :attr:`outcome`, and :attr:`events` for
    typed access; :attr:`raw` exposes the full unprocessed payload.
    """

    transaction_id: TransactionId
    raw: dict[str, Any]

    @property
    def estimated_fee(self) -> Amount:
        """Fee charged in the dry-run execution (µTari).

        Summed from ``raw["finalize"]["fee_receipt"]["cost_breakdown"]["breakdown"]``
        — the engine derives ``FeeReceipt::total_fees_charged`` the same way.
        Returns ``Amount(0)`` if the path is absent.
        """
        from ootle._types.amount import Amount  # noqa: PLC0415

        fee_receipt = _get(_finalize_block(self.raw), "fee_receipt")
        breakdown = _get(_get(fee_receipt, "cost_breakdown"), "breakdown")
        if not isinstance(breakdown, dict):
            return Amount(0)
        total = sum(
            v
            for v in cast("dict[str, Any]", breakdown).values()
            if isinstance(v, int) and not isinstance(v, bool)
        )
        return Amount(total)

    @property
    def outcome(self) -> TransactionOutcome | None:
        """Parsed transaction outcome from the dry-run, or ``None`` if absent.

        Reads ``raw["finalize"]["result"]`` — the engine's ``TransactionResult``
        enum: ``Accept`` → commit, ``AcceptFeeRejectRest`` → fee-only commit
        with a structured :class:`~ootle._types.reject_reason.RejectReason`,
        ``Reject`` → reject with a structured reject reason.
        """
        from ootle._types._reject_reason_json import parse_reject_reason  # noqa: PLC0415
        from ootle._types.outcome import TransactionOutcome as _Outcome  # noqa: PLC0415
        from ootle._types.reject_reason import format_reject_reason  # noqa: PLC0415

        result = _get(_finalize_block(self.raw), "result")
        if not isinstance(result, dict):
            return None
        res = cast("dict[str, Any]", result)
        match res:
            case {"Accept": _}:
                return _Outcome.commit()
            case {"AcceptFeeRejectRest": payload}:
                from ootle._types._reject_reason_json import unwrap_tuple_reason  # noqa: PLC0415

                rr = parse_reject_reason(unwrap_tuple_reason(payload))
                return _Outcome.only_fee_commit(reason=format_reject_reason(rr), reject_reason=rr)
            case {"Reject": payload}:
                rr = parse_reject_reason(payload)
                return _Outcome.reject(reason=format_reject_reason(rr), reject_reason=rr)
            case _:
                return None

    @property
    def events(self) -> tuple[TransactionEvent, ...]:
        """Template events emitted during the dry-run execution.

        Read from ``raw["finalize"]["events"]``.
        """
        from ootle._types._json import parse_event  # noqa: PLC0415

        raw_events = _get(_finalize_block(self.raw), "events")
        if not isinstance(raw_events, list):
            return ()
        return tuple(
            parse_event(cast("dict[str, Any]", e))
            for e in cast("list[Any]", raw_events)
            if isinstance(e, dict)
        )
