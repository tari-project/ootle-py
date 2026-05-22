"""Substate-body parsers for the stealth-UTXO read helpers.

Split out of :mod:`ootle._async._client_stealth_reads` so both files stay under
the 200-line ceiling. Pure functions — they walk the raw indexer substate
envelope (the Python ``Substate`` taxonomy does not yet decode the UTXO variant)
and never touch crypto or I/O.

The on-chain substate is the engine ``Utxo`` shape (``UtxoOutput`` →
``OutputBody``), which differs from the send-side
:class:`~ootle._types.stealth.UnspentOutput`: it carries ``public_nonce`` and no
commitment (derive it from the substate id). See
:mod:`ootle._types.stealth._substate_utxo`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ootle._types.stealth import StealthOutputBody

if TYPE_CHECKING:
    from ootle._types.substate import Substate


def parse_substate_utxo(substate: Substate) -> tuple[bytes, StealthOutputBody] | None:
    """Parse an engine ``Utxo`` substate into ``(commitment, body)``.

    The engine ``OutputBody`` (``Utxo.output.output``) carries no commitment —
    it is derived and lives in the substate id. Returns ``None`` when the
    substate is not a parseable stealth UTXO.
    """
    raw = getattr(substate.value, "raw", None)
    if not isinstance(raw, dict):
        return None
    raw_dict = cast("dict[str, Any]", raw)
    utxo: Any = raw_dict.get("Utxo") or raw_dict.get("UTXO")
    if not isinstance(utxo, dict):
        return None
    outer: Any = cast("dict[str, Any]", utxo).get("output")
    if not isinstance(outer, dict):
        return None
    body: Any = cast("dict[str, Any]", outer).get("output")
    if not isinstance(body, dict):
        return None
    try:
        commitment = bytes.fromhex(substate.id.opaque.rsplit("_", 1)[-1])
        parsed = StealthOutputBody.from_json(cast("dict[str, Any]", body))
    except (TypeError, ValueError, KeyError):
        return None
    return commitment, parsed
