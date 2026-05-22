"""``RejectReason`` — typed model of the engine's rejection reasons.

Mirrors the Rust ``RejectReason`` / ``AbortReason`` enums in
``engine_types::commit_result``. Each variant is a frozen-slots
dataclass with a snake_case ``kind`` literal; the union alias
``RejectReason`` is the discriminated type.

``UnknownRejectReason`` round-trips any variant the v1 client does not
yet decode, so callers can still see *something* when the upstream adds
a new variant ahead of a Python release.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AbortReason = Literal[
    "ForeignPledgeInputConflict",
    "LockInputsFailed",
    "LockOutputsFailed",
    "LockInputsOutputsFailed",
    "ExecutionFailure",
    "OneOrMoreInputsNotFound",
    "InsufficientFeesPaid",
    "FeePaymentInMainIntent",
    "EpochExpired",
]
"""Categorical reason an abort happened — Rust ``AbortReason`` enum.

The TS bindings (v1.30.0) miss ``EpochExpired``; Python follows Rust,
which is the canonical spec.
"""


@dataclass(frozen=True, slots=True)
class ExecutionFailure:
    """Template / engine threw during execution.

    ``message`` is the engine's failure string (e.g. ``"Access Denied: ..."``,
    ``"stack overflow"``, ``"panicked at ..."``).
    """

    message: str
    kind: Literal["execution_failure"] = "execution_failure"


@dataclass(frozen=True, slots=True)
class SubstateNotFound:
    """A referenced substate could not be located."""

    message: str
    kind: Literal["substate_not_found"] = "substate_not_found"


@dataclass(frozen=True, slots=True)
class FailedToLockInputs:
    """Consensus failed to lock the transaction's input substates."""

    message: str
    kind: Literal["failed_to_lock_inputs"] = "failed_to_lock_inputs"


@dataclass(frozen=True, slots=True)
class FailedToLockOutputs:
    """Consensus failed to lock the transaction's output substates."""

    message: str
    kind: Literal["failed_to_lock_outputs"] = "failed_to_lock_outputs"


@dataclass(frozen=True, slots=True)
class ForeignPledgeInputConflict:
    """Unit variant — no payload."""

    kind: Literal["foreign_pledge_input_conflict"] = "foreign_pledge_input_conflict"


@dataclass(frozen=True, slots=True)
class ForeignShardGroupDecidedToAbort:
    """A peer shard group decided to abort the multi-shard transaction."""

    start_shard: int
    end_shard: int
    abort_reason: AbortReason
    kind: Literal["foreign_shard_group_decided_to_abort"] = "foreign_shard_group_decided_to_abort"


@dataclass(frozen=True, slots=True)
class InsufficientFeesPaid:
    """Engine charged less fee than the configured minimum.

    ``message`` typically has the form
    ``"fees of <paid> less than minimum <required>"``.
    """

    message: str
    kind: Literal["insufficient_fees_paid"] = "insufficient_fees_paid"


@dataclass(frozen=True, slots=True)
class FeePaymentInMainIntent:
    """Unit variant — fee instructions were misplaced in the main intent."""

    kind: Literal["fee_payment_in_main_intent"] = "fee_payment_in_main_intent"


@dataclass(frozen=True, slots=True)
class Abort:
    """Generic abort with a structured ``AbortReason`` discriminator."""

    reason: AbortReason
    kind: Literal["abort"] = "abort"


@dataclass(frozen=True, slots=True)
class UnknownRejectReason:
    """Catch-all for variants the v1 client doesn't decode yet.

    Carries the raw JSON payload (object or bare string) so callers can
    inspect it; ``discriminator`` preserves the upstream variant name.
    """

    discriminator: str
    raw: dict[str, Any] | str
    kind: Literal["unknown"] = "unknown"


RejectReason = (
    ExecutionFailure
    | SubstateNotFound
    | FailedToLockInputs
    | FailedToLockOutputs
    | ForeignPledgeInputConflict
    | ForeignShardGroupDecidedToAbort
    | InsufficientFeesPaid
    | FeePaymentInMainIntent
    | Abort
    | UnknownRejectReason
)
"""Typed engine rejection reason (Rust ``RejectReason``)."""


_MessageVariant = (
    ExecutionFailure
    | SubstateNotFound
    | FailedToLockInputs
    | FailedToLockOutputs
    | InsufficientFeesPaid
)


def format_reject_reason(reason: RejectReason) -> str:
    """Render *reason* as a single human-readable line.

    Mirrors the Rust ``impl Display for RejectReason`` in
    ``engine_types::commit_result`` so log lines and ``__str__`` output
    stay aligned with the upstream wire-shape oracle.
    """
    match reason:
        case (
            ExecutionFailure()
            | SubstateNotFound()
            | FailedToLockInputs()
            | FailedToLockOutputs()
            | InsufficientFeesPaid()
        ):
            return f"{_MESSAGE_VARIANT_PREFIXES[type(reason)]}: {reason.message}"
        case ForeignShardGroupDecidedToAbort():
            return (
                f"Foreign shard group [{reason.start_shard}, {reason.end_shard}] "
                f"decided to abort: {reason.abort_reason}"
            )
        case Abort():
            return f"Abort: {reason.reason}"
        case ForeignPledgeInputConflict():
            return "Foreign pledge input conflict"
        case FeePaymentInMainIntent():
            return "Fee payment in main intent"
        case UnknownRejectReason():
            return f"Unknown: {reason.discriminator}"
        case _:
            raise AssertionError(f"unhandled variant: {reason!r}")


_MESSAGE_VARIANT_PREFIXES: dict[type[_MessageVariant], str] = {
    ExecutionFailure: "Execution failure",
    SubstateNotFound: "Substate not found",
    FailedToLockInputs: "Failed to lock inputs",
    FailedToLockOutputs: "Failed to lock outputs",
    InsufficientFeesPaid: "Insufficient fees paid",
}
