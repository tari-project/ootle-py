"""``RejectReason`` parser + ``format_reject_reason`` coverage.

The parser must accept both externally-tagged serde shapes (bare string
for unit variants; single-key object for newtype / struct variants) and
fall back to :class:`UnknownRejectReason` for variants the v1 client
does not yet decode.
"""

from __future__ import annotations

import pytest

from ootle._types._reject_reason_json import parse_reject_reason
from ootle._types.reject_reason import (
    Abort,
    ExecutionFailure,
    FailedToLockInputs,
    FailedToLockOutputs,
    FeePaymentInMainIntent,
    ForeignPledgeInputConflict,
    ForeignShardGroupDecidedToAbort,
    InsufficientFeesPaid,
    SubstateNotFound,
    UnknownRejectReason,
    format_reject_reason,
)


def test_parse_unit_variant_foreign_pledge_input_conflict() -> None:
    assert parse_reject_reason("ForeignPledgeInputConflict") == ForeignPledgeInputConflict()


def test_parse_unit_variant_fee_payment_in_main_intent() -> None:
    assert parse_reject_reason("FeePaymentInMainIntent") == FeePaymentInMainIntent()


def test_parse_execution_failure_extracts_message() -> None:
    parsed = parse_reject_reason({"ExecutionFailure": "stack overflow"})
    assert parsed == ExecutionFailure(message="stack overflow")


def test_parse_substate_not_found_extracts_message() -> None:
    assert parse_reject_reason({"SubstateNotFound": "missing"}) == SubstateNotFound(
        message="missing"
    )


def test_parse_failed_to_lock_inputs_extracts_message() -> None:
    assert parse_reject_reason({"FailedToLockInputs": "x"}) == FailedToLockInputs(message="x")


def test_parse_failed_to_lock_outputs_extracts_message() -> None:
    assert parse_reject_reason({"FailedToLockOutputs": "y"}) == FailedToLockOutputs(message="y")


def test_parse_insufficient_fees_paid_extracts_message() -> None:
    parsed = parse_reject_reason({"InsufficientFeesPaid": "fees of 100 less than minimum 500"})
    assert parsed == InsufficientFeesPaid(message="fees of 100 less than minimum 500")


def test_parse_abort_extracts_abort_reason() -> None:
    parsed = parse_reject_reason({"Abort": {"reason": "ExecutionFailure"}})
    assert parsed == Abort(reason="ExecutionFailure")


def test_parse_foreign_shard_group_decided_to_abort_extracts_fields() -> None:
    parsed = parse_reject_reason(
        {
            "ForeignShardGroupDecidedToAbort": {
                "start_shard": 0,
                "end_shard": 7,
                "abort_reason": "LockInputsFailed",
            }
        }
    )
    assert parsed == ForeignShardGroupDecidedToAbort(
        start_shard=0, end_shard=7, abort_reason="LockInputsFailed"
    )


def test_parse_unknown_variant_round_trips_raw() -> None:
    raw = {"FutureVariant": {"extra": 1}}
    parsed = parse_reject_reason(raw)
    assert isinstance(parsed, UnknownRejectReason)
    assert parsed.discriminator == "FutureVariant"
    assert parsed.raw == raw


def test_parse_unknown_unit_variant_round_trips_string() -> None:
    parsed = parse_reject_reason("BrandNewUnit")
    assert isinstance(parsed, UnknownRejectReason)
    assert parsed.discriminator == "BrandNewUnit"
    assert parsed.raw == "BrandNewUnit"


def test_parse_rejects_non_object_non_string() -> None:
    with pytest.raises(TypeError, match="RejectReason must be"):
        parse_reject_reason(42)


def test_parse_rejects_multi_key_object() -> None:
    with pytest.raises(TypeError, match="RejectReason must be"):
        parse_reject_reason({"A": 1, "B": 2})


def test_parse_rejects_unknown_abort_reason() -> None:
    with pytest.raises(ValueError, match="unknown AbortReason"):
        parse_reject_reason({"Abort": {"reason": "NotARealReason"}})


def test_parse_epoch_expired_abort_reason() -> None:
    """``EpochExpired`` is present in Rust but missing from TS v1.30.0 — Python follows Rust."""
    assert parse_reject_reason({"Abort": {"reason": "EpochExpired"}}) == Abort(
        reason="EpochExpired"
    )


def test_format_reject_reason_matches_rust_display() -> None:
    assert format_reject_reason(ExecutionFailure("boom")) == "Execution failure: boom"
    assert (
        format_reject_reason(InsufficientFeesPaid("fees of 100 less than minimum 500"))
        == "Insufficient fees paid: fees of 100 less than minimum 500"
    )
    assert format_reject_reason(SubstateNotFound("x")) == "Substate not found: x"
    assert format_reject_reason(FailedToLockInputs("x")) == "Failed to lock inputs: x"
    assert format_reject_reason(FailedToLockOutputs("x")) == "Failed to lock outputs: x"
    assert format_reject_reason(ForeignPledgeInputConflict()) == "Foreign pledge input conflict"
    assert format_reject_reason(FeePaymentInMainIntent()) == "Fee payment in main intent"
    assert format_reject_reason(Abort(reason="ExecutionFailure")) == "Abort: ExecutionFailure"
    assert (
        format_reject_reason(
            ForeignShardGroupDecidedToAbort(
                start_shard=1, end_shard=4, abort_reason="LockInputsFailed"
            )
        )
        == "Foreign shard group [1, 4] decided to abort: LockInputsFailed"
    )
    assert (
        format_reject_reason(UnknownRejectReason(discriminator="Mystery", raw="Mystery"))
        == "Unknown: Mystery"
    )
