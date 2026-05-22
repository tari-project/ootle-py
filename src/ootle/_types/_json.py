"""JSON serde helpers for indexer ↔ client wire shapes.

These are hand-rolled — no pydantic. Each parser raises ``KeyError`` /
``TypeError`` / ``ValueError`` on malformed input and lets the transport
layer wrap with :class:`IndexerClientError`.
"""

from __future__ import annotations

from typing import Any

from ootle._types._json_helpers import (
    as_dict,
    as_str,
    optional_dict,
    optional_list,
    require_dict,
    require_int,
    require_str,
)
from ootle._types.address import TemplateAddress
from ootle._types.amount import Amount
from ootle._types.diff_summary import DiffSummary, UpSubstate
from ootle._types.events import TransactionEvent
from ootle._types.receipt import FeeReceipt, TransactionReceipt
from ootle._types.substate import SubstateId
from ootle._types.transaction import TransactionId


def hex_to_bytes(s: str) -> bytes:
    """Decode a hex string. Tolerates a leading ``0x`` prefix."""
    if s.startswith(("0x", "0X")):
        s = s[2:]
    return bytes.fromhex(s)


def bytes_to_hex(b: bytes) -> str:
    """Encode bytes as a lowercase hex string with no prefix."""
    return b.hex()


def parse_event(payload: dict[str, Any]) -> TransactionEvent:
    """Parse a ``TransactionEvent`` envelope as the REST API returns it.

    The receipt-attached form is flat — ``{topic, payload, template_address,
    substate_id}`` — and carries neither an ``id`` nor a ``transaction_id``
    (those only exist on the SSE wire shape; see :func:`parse_sse_event`).
    """
    template = payload.get("template_address")
    if template is not None and not isinstance(template, str):
        msg = "event `template_address` must be a string when present"
        raise TypeError(msg)
    substate = payload.get("substate_id")
    if substate is not None and not isinstance(substate, str):
        msg = "event `substate_id` must be a string when present"
        raise TypeError(msg)
    return TransactionEvent(
        topic=require_str(payload, "topic"),
        payload=optional_dict(payload, "payload") or {},
        template_address=TemplateAddress(template) if template is not None else None,
        substate_id=SubstateId(substate) if substate is not None else None,
    )


def _parse_sse_id(raw: str) -> int | None:
    """Best-effort parse of an SSE ``id:`` line into an ``int``.

    SSE ids are server-controlled free-form strings per the spec; a
    non-empty, non-numeric id (e.g. a proxy-injected UUID) has no integer
    interpretation, so ``None`` — the field's existing optional default — is
    the safe fallback rather than a raw ``ValueError``.
    """
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def parse_sse_event(sse_topic: str, sse_id: str, payload: dict[str, Any]) -> TransactionEvent:
    """Parse a ``TransactionEvent`` from the indexer SSE stream.

    The indexer transmits the topic via the SSE ``event:`` line and the
    numeric event id via the SSE ``id:`` line. The JSON body carries
    ``{transaction_id, event: {substate_id, template_address, payload}}``.
    """
    inner = require_dict(payload, "event")
    template = inner.get("template_address")
    if template is not None and not isinstance(template, str):
        msg = "event `template_address` must be a string when present"
        raise TypeError(msg)
    substate = inner.get("substate_id")
    if substate is not None and not isinstance(substate, str):
        msg = "event `substate_id` must be a string when present"
        raise TypeError(msg)
    tx_id = payload.get("transaction_id")
    if tx_id is not None and not isinstance(tx_id, str):
        msg = "event `transaction_id` must be a string when present"
        raise TypeError(msg)
    return TransactionEvent(
        topic=sse_topic,
        payload=optional_dict(inner, "payload") or {},
        template_address=TemplateAddress(template) if template is not None else None,
        substate_id=SubstateId(substate) if substate is not None else None,
        id=_parse_sse_id(sse_id),
        transaction_id=TransactionId(tx_id) if tx_id is not None else None,
    )


def parse_receipt(payload: dict[str, Any]) -> TransactionReceipt:
    """Parse a ``TransactionReceipt`` envelope."""
    fee = require_dict(payload, "fee_receipt")
    breakdown = optional_dict(optional_dict(fee, "cost_breakdown") or {}, "breakdown") or {}
    events_raw = optional_list(payload, "events") or []
    logs_raw = optional_list(payload, "logs") or []
    return TransactionReceipt(
        epoch=require_int(payload, "epoch"),
        fee_receipt=FeeReceipt(
            total_fee_payment=Amount(require_int(fee, "total_fee_payment")),
            total_fees_paid=Amount(require_int(fee, "total_fees_paid")),
            total_fee_overcharge=Amount(require_int(fee, "total_fee_overcharge")),
            cost_breakdown={k: require_int(breakdown, k) for k in breakdown},
        ),
        events=tuple(parse_event(as_dict(e)) for e in events_raw),
        logs=tuple(as_str(line) for line in logs_raw),
        diff_summary=parse_diff_summary(optional_dict(payload, "diff_summary") or {}),
    )


def parse_diff_summary(payload: dict[str, Any]) -> DiffSummary:
    """Parse a ``DiffSummary`` envelope. Missing ``upped`` → empty."""
    upped_raw = optional_list(payload, "upped") or []
    return DiffSummary(upped=tuple(_parse_up_substate(as_dict(u)) for u in upped_raw))


def _parse_up_substate(payload: dict[str, Any]) -> UpSubstate:
    return UpSubstate(
        substate_id=SubstateId(opaque=require_str(payload, "substate_id")),
        version=require_int(payload, "version"),
        value_hash=require_str(payload, "value_hash"),
    )
