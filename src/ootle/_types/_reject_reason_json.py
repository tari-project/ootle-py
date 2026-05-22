"""JSON parser for the engine's ``RejectReason`` enum.

Distinct from :mod:`ootle._types._json` so the file stays under the
200-line limit. Accepts both shapes that externally-tagged serde
produces:

- Bare string for unit variants
  (``"ForeignPledgeInputConflict"``, ``"FeePaymentInMainIntent"``)
- Single-key object for newtype / struct variants
  (``{"ExecutionFailure": "msg"}``, ``{"Abort": {"reason": "..."}}``)
"""

from __future__ import annotations

from typing import Any, cast, get_args

from ootle._types._json_helpers import as_dict, as_str, require_int
from ootle._types.reject_reason import (
    Abort,
    AbortReason,
    ExecutionFailure,
    FailedToLockInputs,
    FailedToLockOutputs,
    FeePaymentInMainIntent,
    ForeignPledgeInputConflict,
    ForeignShardGroupDecidedToAbort,
    InsufficientFeesPaid,
    RejectReason,
    SubstateNotFound,
    UnknownRejectReason,
)

_ABORT_REASON_VARIANTS: frozenset[str] = frozenset(get_args(AbortReason))

# Newtype variants whose payload is a single string message.
_STRING_NEWTYPE_VARIANTS: dict[
    str,
    type[
        ExecutionFailure
        | SubstateNotFound
        | FailedToLockInputs
        | FailedToLockOutputs
        | InsufficientFeesPaid
    ],
] = {
    "ExecutionFailure": ExecutionFailure,
    "SubstateNotFound": SubstateNotFound,
    "FailedToLockInputs": FailedToLockInputs,
    "FailedToLockOutputs": FailedToLockOutputs,
    "InsufficientFeesPaid": InsufficientFeesPaid,
}


def parse_reject_reason(value: Any) -> RejectReason:
    """Parse a JSON-encoded engine ``RejectReason``.

    Returns :class:`UnknownRejectReason` for any variant not in the v1
    set, so callers see *something* when upstream adds a variant.
    """
    if isinstance(value, str):
        if value == "ForeignPledgeInputConflict":
            return ForeignPledgeInputConflict()
        if value == "FeePaymentInMainIntent":
            return FeePaymentInMainIntent()
        return UnknownRejectReason(discriminator=value, raw=value)

    if not isinstance(value, dict):
        msg = f"RejectReason must be a string or single-key object, got {type(value).__name__}"
        raise TypeError(msg)

    items: dict[str, Any] = cast("dict[str, Any]", value)
    if len(items) != 1:
        msg = f"RejectReason must be a single-key object, got {len(items)} keys"
        raise TypeError(msg)
    variant, payload = next(iter(items.items()))
    return _parse_object_variant(variant, payload, items)


def unwrap_tuple_reason(rest: Any) -> Any:
    """Pull the ``RejectReason`` element out of a serde tuple-variant payload.

    ``AcceptFeeRejectRest`` serializes as ``[SubstateDiff, RejectReason]``;
    the reason sits in the last slot. Empty / non-list payloads round-trip
    so callers can hand the result straight to :func:`parse_reject_reason`
    and let it complain.
    """
    if isinstance(rest, list):
        items: list[Any] = cast("list[Any]", rest)
        if items:
            return items[-1]
    return cast("Any", rest)


def _parse_object_variant(variant: str, payload: Any, items: dict[str, Any]) -> RejectReason:
    string_ctor = _STRING_NEWTYPE_VARIANTS.get(variant)
    if string_ctor is not None:
        return string_ctor(message=as_str(payload))
    if variant == "Abort":
        return Abort(reason=_as_abort_reason(as_dict(payload).get("reason")))
    if variant == "ForeignShardGroupDecidedToAbort":
        body = as_dict(payload)
        return ForeignShardGroupDecidedToAbort(
            start_shard=require_int(body, "start_shard"),
            end_shard=require_int(body, "end_shard"),
            abort_reason=_as_abort_reason(body.get("abort_reason")),
        )
    return UnknownRejectReason(discriminator=variant, raw=items)


def _as_abort_reason(value: Any) -> AbortReason:
    if isinstance(value, str) and value in _ABORT_REASON_VARIANTS:
        return cast("AbortReason", value)
    msg = f"unknown AbortReason variant: {value!r}"
    raise ValueError(msg)
