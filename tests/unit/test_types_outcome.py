"""``TransactionOutcome`` constructors and predicates."""

from __future__ import annotations

from ootle._types.outcome import TransactionOutcome


def test_commit_constructor_has_no_reason() -> None:
    o = TransactionOutcome.commit()
    assert o.kind == "commit"
    assert o.reason is None
    assert o.is_commit
    assert not o.is_only_fee_commit
    assert not o.is_reject


def test_only_fee_commit_carries_reason() -> None:
    o = TransactionOutcome.only_fee_commit("validator-rejection")
    assert o.kind == "only_fee_commit"
    assert o.reason == "validator-rejection"
    assert o.is_only_fee_commit
    assert not o.is_commit
    assert not o.is_reject


def test_reject_carries_reason() -> None:
    o = TransactionOutcome.reject("missing-fee")
    assert o.kind == "reject"
    assert o.reason == "missing-fee"
    assert o.is_reject
    assert not o.is_commit
    assert not o.is_only_fee_commit


def test_outcome_is_frozen_and_hashable() -> None:
    a = TransactionOutcome.commit()
    b = TransactionOutcome.commit()
    assert a == b
    assert hash(a) == hash(b)
