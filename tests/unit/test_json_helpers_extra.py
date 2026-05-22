"""Coverage for the type-guard branches in ``_types/_json``."""

from __future__ import annotations

from typing import Any

import pytest

from ootle._types._json import (
    parse_diff_summary,
    parse_event,
    parse_receipt,
    parse_sse_event,
)

_FEE_RECEIPT: dict[str, Any] = {
    "total_fee_payment": 0,
    "total_fees_paid": 0,
    "total_fee_overcharge": 0,
    "cost_breakdown": {"breakdown": {}},
}


def test_parse_event_rejects_non_string_template_address() -> None:
    with pytest.raises(TypeError, match="template_address"):
        parse_event({"topic": "T", "template_address": 5})


def test_parse_event_rejects_non_string_substate_id() -> None:
    with pytest.raises(TypeError, match="substate_id"):
        parse_event({"topic": "T", "substate_id": 5})


def test_parse_receipt_rejects_non_list_events() -> None:
    with pytest.raises(TypeError, match="must be an array"):
        parse_receipt({"epoch": 1, "fee_receipt": _FEE_RECEIPT, "events": "not-a-list"})


def test_parse_receipt_rejects_non_dict_event_entry() -> None:
    with pytest.raises(TypeError, match="expected an object"):
        parse_receipt({"epoch": 1, "fee_receipt": _FEE_RECEIPT, "events": ["not-a-dict"]})


def test_parse_receipt_rejects_non_string_log_entry() -> None:
    with pytest.raises(TypeError, match="expected a string"):
        parse_receipt({"epoch": 1, "fee_receipt": _FEE_RECEIPT, "logs": [42]})


def test_parse_diff_summary_empty_when_upped_missing() -> None:
    assert parse_diff_summary({}).upped == ()


def test_parse_diff_summary_rejects_non_list_upped() -> None:
    with pytest.raises(TypeError, match="must be an array"):
        parse_diff_summary({"upped": "not-a-list"})


def test_parse_diff_summary_rejects_non_dict_entry() -> None:
    with pytest.raises(TypeError, match="expected an object"):
        parse_diff_summary({"upped": ["not-a-dict"]})


def test_parse_diff_summary_rejects_non_string_substate_id() -> None:
    with pytest.raises(TypeError, match="substate_id"):
        parse_diff_summary({"upped": [{"substate_id": 7, "version": 0, "value_hash": "f0"}]})


def test_parse_sse_event_numeric_id() -> None:
    ev = parse_sse_event("T::E", "42", {"event": {}})
    assert ev.id == 42


def test_parse_sse_event_empty_id_is_none() -> None:
    ev = parse_sse_event("T::E", "", {"event": {}})
    assert ev.id is None


def test_parse_sse_event_non_numeric_id_is_none_no_raise() -> None:
    ev = parse_sse_event("T::E", "9f1c-uuid-style", {"event": {}})
    assert ev.id is None
    assert ev.topic == "T::E"
