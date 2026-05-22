"""JSON parsers for the indexer's wire shapes.

Distinct from :mod:`ootle._types._json` so the file stays under the
200-line limit. These helpers map the routes exposed by
``tari_indexer_client`` to the project's domain types:

- ``GET network`` → :class:`NetworkInfo`
- ``GET substates/{id}`` → :class:`Substate`
- ``POST substates/fetch`` → ``dict[SubstateId, Substate]``
- ``POST transactions`` → :class:`TransactionId`
- ``GET transactions/{id}/result`` → tuple ``(is_finalized, outcome | None)``
"""

from __future__ import annotations

from typing import Any, cast

from ootle._types._json_helpers import require_dict, require_int, require_str
from ootle._types._reject_reason_json import parse_reject_reason, unwrap_tuple_reason
from ootle._types._substate_json import parse_substate_value
from ootle._types.network import Network, NetworkInfo
from ootle._types.outcome import TransactionOutcome
from ootle._types.reject_reason import format_reject_reason
from ootle._types.substate import Substate, SubstateId
from ootle._types.transaction import TransactionId


def parse_network_info(payload: dict[str, Any]) -> NetworkInfo:
    """Parse ``GET network`` → :class:`NetworkInfo`.

    The indexer returns ``{network: "<name>", network_byte: <u8>, epoch: <int>}``.
    We resolve :class:`Network` from the integer ``network_byte``; the
    string ``network`` field is informational.
    """
    return NetworkInfo(
        network=Network(require_int(payload, "network_byte")),
        epoch=require_int(payload, "epoch"),
    )


def parse_indexer_substate(id_: SubstateId, payload: dict[str, Any]) -> Substate:
    """Parse ``GET substates/{id}`` → :class:`Substate`.

    The response shape is ``{version, substate}`` (no ``id``); the id is
    the URL parameter. We synthesise the envelope by attaching ``id_``.
    """
    return Substate(
        id=id_,
        version=require_int(payload, "version"),
        value=parse_substate_value(require_dict(payload, "substate")),
    )


def parse_indexer_substates_map(payload: dict[str, Any]) -> dict[SubstateId, Substate]:
    """Parse ``POST substates/fetch`` → ``{SubstateId: Substate}``.

    The indexer returns ``{substates: {<id>: {version, substate, ...}}}``.
    Missing-from-result substates are simply absent from the map.
    """
    raw = require_dict(payload, "substates")
    result: dict[SubstateId, Substate] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            msg = f"substates['{key}'] must be an object, got {type(value).__name__}"
            raise TypeError(msg)
        sub_id = SubstateId(key)
        result[sub_id] = parse_indexer_substate(sub_id, cast("dict[str, Any]", value))
    return result


def parse_submit_response(payload: dict[str, Any]) -> TransactionId:
    """Parse ``POST /transactions`` → :class:`TransactionId`."""
    return TransactionId(require_str(payload, "transaction_id"))


def parse_transaction_result(payload: dict[str, Any]) -> tuple[bool, TransactionOutcome | None]:
    """Parse ``GET /transactions/{id}/result`` → ``(is_finalized, outcome | None)``.

    Returns ``(False, None)`` for the ``Pending`` variant. For
    ``Finalized``, returns ``(True, outcome)`` where outcome reflects
    ``final_decision`` + ``execution_result.finalize.result``.
    """
    result = payload.get("result")
    if result == "Pending":
        return False, None
    if not isinstance(result, dict):
        msg = "expected `result` to be 'Pending' or an object"
        raise TypeError(msg)
    finalized = cast("dict[str, Any]", result).get("Finalized")
    if not isinstance(finalized, dict):
        msg = "expected `result.Finalized` to be an object"
        raise TypeError(msg)
    fin = cast("dict[str, Any]", finalized)
    return True, _decode_finalized(fin)


def _decode_finalized(fin: dict[str, Any]) -> TransactionOutcome:
    decision = fin.get("final_decision")
    raw_details = fin.get("abort_details")
    abort_details = "Unknown" if raw_details is None else raw_details
    engine_result = _engine_result(fin)

    if decision == "Commit":
        match engine_result:
            case {"AcceptFeeRejectRest": rest}:
                rr = parse_reject_reason(unwrap_tuple_reason(rest))
                return TransactionOutcome.only_fee_commit(
                    reason=format_reject_reason(rr), reject_reason=rr
                )
            case _:
                return TransactionOutcome.commit()

    match engine_result:
        case {"Reject": payload}:
            rr = parse_reject_reason(payload)
            return TransactionOutcome.reject(reason=format_reject_reason(rr), reject_reason=rr)
        case _:
            return TransactionOutcome.reject(_stringify(abort_details))


def _engine_result(fin: dict[str, Any]) -> Any:
    exec_result = fin.get("execution_result")
    if not isinstance(exec_result, dict):
        return None
    finalize = cast("dict[str, Any]", exec_result).get("finalize")
    if not isinstance(finalize, dict):
        return None
    return cast("dict[str, Any]", finalize).get("result")


def _stringify(value: object) -> str:
    if isinstance(value, str):
        return value
    return repr(value)
