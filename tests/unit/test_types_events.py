"""``TransactionEvent`` and ``TransactionEventFilter`` construction."""

from __future__ import annotations

from ootle._types.address import TemplateAddress
from ootle._types.events import TransactionEvent, TransactionEventFilter
from ootle._types.substate import SubstateId


def test_transaction_event_default_payload_is_empty_dict() -> None:
    ev = TransactionEvent(topic="MyTpl::Sent")
    assert ev.topic == "MyTpl::Sent"
    assert ev.payload == {}
    assert ev.template_address is None
    assert ev.substate_id is None


def test_transaction_event_carries_optional_origin() -> None:
    ev = TransactionEvent(
        topic="MyTpl::Sent",
        payload={"amount": 100},
        template_address=TemplateAddress("t-1"),
        substate_id=SubstateId("c-1"),
    )
    assert ev.payload == {"amount": 100}
    assert ev.template_address == TemplateAddress("t-1")
    assert ev.substate_id == SubstateId("c-1")


def test_default_filter_is_all_wildcards() -> None:
    f = TransactionEventFilter()
    assert f.topic is None
    assert f.substate_id is None
    assert f.template_address is None


def test_filter_can_pin_each_field() -> None:
    f = TransactionEventFilter(
        topic="MyTpl::Sent",
        substate_id=SubstateId("c-1"),
        template_address=TemplateAddress("t-1"),
    )
    assert f.topic == "MyTpl::Sent"
