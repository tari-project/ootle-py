"""``TransactionRequest`` builder behaviour, wrapper hashing, DryRunResult properties."""

from __future__ import annotations

from typing import Any

from ootle._types.outcome import TransactionOutcome
from ootle._types.reject_reason import ExecutionFailure, InsufficientFeesPaid
from ootle._types.transaction import (
    DryRunResult,
    Transaction,
    TransactionAuthorization,
    TransactionId,
    TransactionRequest,
    UnsignedTransaction,
)


def _dry_run(raw: dict[str, Any]) -> DryRunResult:
    return DryRunResult(transaction_id=TransactionId("abc"), raw=raw)


def test_with_transaction_returns_new_instance() -> None:
    req = TransactionRequest()
    tx = UnsignedTransaction(json="{}")
    new = req.with_transaction(tx)
    assert new is not req
    assert new.transaction is tx
    assert req.transaction is None


def test_add_authorization_is_non_mutating_and_preserves_order() -> None:
    req = TransactionRequest()
    a = TransactionAuthorization(json="A")
    b = TransactionAuthorization(json="B")
    s1 = req.add_authorization(a)
    s2 = s1.add_authorization(b)
    assert req.authorizations == ()
    assert s1.authorizations == (a,)
    assert s2.authorizations == (a, b)


def test_with_authorizations_replaces_tuple() -> None:
    req = TransactionRequest(
        authorizations=(TransactionAuthorization(json="X"),),
    )
    a = TransactionAuthorization(json="A")
    b = TransactionAuthorization(json="B")
    new = req.with_authorizations([a, b])
    assert new.authorizations == (a, b)


def test_unsigned_and_sealed_wrappers_are_hashable() -> None:
    a = UnsignedTransaction(json="x")
    b = UnsignedTransaction(json="x")
    c = Transaction(json="x")
    assert a == b
    assert hash(a) == hash(b)
    # Different wrapper types — equal json must NOT collide as same value
    assert a != c
    assert {a, b, c} == {a, c}


def test_authorization_dataclass_equality() -> None:
    a = TransactionAuthorization(json="auth")
    b = TransactionAuthorization(json="auth")
    assert a == b
    assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# DryRunResult — shapes mirror the engine ``ExecuteResult`` JSON (see
# crates/engine_types/src/{commit_result,fees}.rs).
# ---------------------------------------------------------------------------


def _finalize(**fields: Any) -> dict[str, Any]:
    return {"finalize": fields, "execution_time": {"secs": 0, "nanos": 1}, "execute_epoch": 3}


def _fee_receipt(breakdown: dict[str, int]) -> dict[str, Any]:
    return {
        "total_fee_payment": 1000,
        "total_fees_paid": sum(breakdown.values()),
        "total_fee_overcharge": 0,
        "cost_breakdown": {"breakdown": breakdown},
    }


def test_dry_run_estimated_fee_sums_cost_breakdown() -> None:
    breakdown = {"RuntimeCall": 14, "Storage": 90, "TemplateLoad": 450}
    raw = _finalize(fee_receipt=_fee_receipt(breakdown))
    assert _dry_run(raw).estimated_fee == 554


def test_dry_run_estimated_fee_zero_on_empty_breakdown() -> None:
    raw = _finalize(fee_receipt=_fee_receipt({}))
    assert _dry_run(raw).estimated_fee == 0


def test_dry_run_estimated_fee_returns_zero_on_missing_path() -> None:
    assert _dry_run({}).estimated_fee == 0


def test_dry_run_estimated_fee_accepts_bare_finalize_block() -> None:
    raw = {"fee_receipt": _fee_receipt({"Initial": 7})}
    assert _dry_run(raw).estimated_fee == 7


def test_dry_run_outcome_commit() -> None:
    raw = _finalize(result={"Accept": {"up_substates": [], "down_substates": []}})
    assert _dry_run(raw).outcome == TransactionOutcome.commit()


def test_dry_run_outcome_reject_with_reason() -> None:
    raw = _finalize(result={"Reject": {"ExecutionFailure": "out of gas"}})
    outcome = _dry_run(raw).outcome
    assert outcome is not None
    assert outcome.is_reject
    assert outcome.reject_reason == ExecutionFailure(message="out of gas")
    assert "Execution failure" in (outcome.reason or "")


def test_dry_run_outcome_fee_only_commit_extracts_reject_reason() -> None:
    raw = _finalize(
        result={
            "AcceptFeeRejectRest": [
                {"up_substates": []},
                {"InsufficientFeesPaid": "fees of 100 less than minimum 500"},
            ]
        }
    )
    outcome = _dry_run(raw).outcome
    assert outcome is not None
    assert outcome.is_only_fee_commit
    assert outcome.reject_reason == InsufficientFeesPaid(
        message="fees of 100 less than minimum 500"
    )
    assert "Insufficient fees paid" in (outcome.reason or "")


def test_dry_run_outcome_none_on_missing() -> None:
    assert _dry_run({}).outcome is None


def test_dry_run_outcome_none_on_unknown_variant() -> None:
    assert _dry_run(_finalize(result={"Mystery": 1})).outcome is None


def test_dry_run_events_empty_on_missing() -> None:
    assert _dry_run({}).events == ()


def test_dry_run_events_parsed_from_raw() -> None:
    event_raw: dict[str, Any] = {"topic": "std.component.created", "payload": {}}
    raw = _finalize(events=[event_raw], result={"Accept": {}})
    events = _dry_run(raw).events
    assert len(events) == 1
    assert events[0].topic == "std.component.created"


def test_empty_finalize_block_is_not_conflated_with_raw() -> None:
    """A present-but-empty ``finalize: {}`` must read from the empty block,
    not silently fall back to the top-level payload (item 09)."""
    raw: dict[str, Any] = {
        "finalize": {},
        # Decoys at the wrong level — must NOT be picked up via fallback.
        "result": {"Accept": {}},
        "fee_receipt": _fee_receipt({"Storage": 99}),
        "events": [{"topic": "std.decoy", "payload": {}}],
    }
    result = _dry_run(raw)
    assert result.outcome is None
    assert result.estimated_fee == 0
    assert result.events == ()
