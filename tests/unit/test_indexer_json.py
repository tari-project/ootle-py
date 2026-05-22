"""Coverage for ``ootle._types._indexer_json`` parsers + type guards."""

from __future__ import annotations

from typing import Any

import pytest

from ootle._types._indexer_json import (
    parse_indexer_substates_map,
    parse_submit_response,
    parse_transaction_result,
)
from ootle._types.reject_reason import ExecutionFailure, InsufficientFeesPaid


def test_substates_map_rejects_non_object_value() -> None:
    with pytest.raises(TypeError, match="must be an object"):
        parse_indexer_substates_map({"substates": {"x": "not-an-object"}})


def test_submit_response_extracts_transaction_id() -> None:
    tx_id = parse_submit_response({"transaction_id": "tx_abc"})
    assert tx_id == "tx_abc"


def test_submit_response_rejects_non_string_id() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_submit_response({"transaction_id": 42})


def test_transaction_result_pending_returns_falsy() -> None:
    is_finalized, outcome = parse_transaction_result({"result": "Pending"})
    assert is_finalized is False
    assert outcome is None


def test_transaction_result_rejects_non_object_result() -> None:
    with pytest.raises(TypeError, match="'Pending' or an object"):
        parse_transaction_result({"result": 42})


def test_transaction_result_rejects_non_object_finalized() -> None:
    with pytest.raises(TypeError, match=r"`result\.Finalized` to be an object"):
        parse_transaction_result({"result": {"Finalized": "not-an-object"}})


def test_transaction_result_commit_decision() -> None:
    payload = {"result": {"Finalized": {"final_decision": "Commit"}}}
    is_finalized, outcome = parse_transaction_result(payload)
    assert is_finalized is True
    assert outcome is not None
    assert not outcome.is_reject


def test_transaction_result_only_fee_commit_extracts_typed_reject_reason() -> None:
    """When ``final_decision`` is ``Commit`` and the engine result is
    ``AcceptFeeRejectRest``, the outcome is fee-only-commit with the
    structured reject reason extracted from the tuple's reason slot.
    Cross-cuts the Bug 02 split (consensus decision vs engine result).
    """
    payload: dict[str, Any] = {
        "result": {
            "Finalized": {
                "final_decision": "Commit",
                "execution_result": {
                    "finalize": {
                        "result": {
                            "AcceptFeeRejectRest": [
                                {"up_substates": []},
                                {"InsufficientFeesPaid": "fees of 100 less than minimum 500"},
                            ]
                        }
                    }
                },
            }
        }
    }
    is_finalized, outcome = parse_transaction_result(payload)
    assert is_finalized is True
    assert outcome is not None
    assert outcome.is_only_fee_commit
    assert outcome.reject_reason == InsufficientFeesPaid(
        message="fees of 100 less than minimum 500"
    )
    assert "Insufficient fees paid" in (outcome.reason or "")


def test_transaction_result_reject_extracts_typed_reject_reason() -> None:
    payload: dict[str, Any] = {
        "result": {
            "Finalized": {
                "final_decision": "Reject",
                "abort_details": "Execution failure: stack overflow",
                "execution_result": {
                    "finalize": {"result": {"Reject": {"ExecutionFailure": "stack overflow"}}}
                },
            }
        }
    }
    _, outcome = parse_transaction_result(payload)
    assert outcome is not None
    assert outcome.is_reject
    assert outcome.reject_reason == ExecutionFailure(message="stack overflow")
    assert "Execution failure" in (outcome.reason or "")


def test_transaction_result_reject_falls_back_to_abort_details() -> None:
    payload = {
        "result": {
            "Finalized": {
                "final_decision": "Reject",
                "abort_details": "engine fault",
            }
        }
    }
    is_finalized, outcome = parse_transaction_result(payload)
    assert is_finalized is True
    assert outcome is not None
    assert outcome.is_reject
    assert outcome.reason == "engine fault"
    assert outcome.reject_reason is None


def test_transaction_result_default_abort_details_when_missing() -> None:
    payload = {"result": {"Finalized": {"final_decision": "Reject"}}}
    is_finalized, outcome = parse_transaction_result(payload)
    assert is_finalized is True
    assert outcome is not None
    assert outcome.reason == "Unknown"


def test_transaction_result_preserves_empty_abort_details() -> None:
    """An explicit ``"abort_details": ""`` must round-trip as ``""`` rather
    than being rewritten to ``"Unknown"`` (regression for bug #03)."""
    payload = {
        "result": {
            "Finalized": {
                "final_decision": "Reject",
                "abort_details": "",
            }
        }
    }
    _, outcome = parse_transaction_result(payload)
    assert outcome is not None
    assert outcome.reason == ""
