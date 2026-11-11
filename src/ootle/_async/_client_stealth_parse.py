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


_UTXO_ID_PREFIX = "utxo"
_COMMITMENT_LEN = 32


def parse_substate_utxo(substate: Substate) -> tuple[bytes, StealthOutputBody] | None:
    """Parse an engine ``Utxo`` substate into ``(commitment, body)``.

    The engine ``OutputBody`` (``Utxo.output.output``) carries no commitment —
    it is derived and lives in the substate id. Returns ``None`` when the
    substate is not a live, spendable stealth UTXO.
    """
    raw = getattr(substate.value, "raw", None)
    if not isinstance(raw, dict):
        return None
    raw_dict = cast("dict[str, Any]", raw)
    utxo: Any = raw_dict.get("Utxo") or raw_dict.get("UTXO")
    if not isinstance(utxo, dict):
        return None
    utxo_dict = cast("dict[str, Any]", utxo)
    if utxo_dict.get("is_frozen") is True:
        return None
    outer: Any = utxo_dict.get("output")
    if not isinstance(outer, dict):
        return None
    body: Any = cast("dict[str, Any]", outer).get("output")
    if not isinstance(body, dict):
        return None
    parts = substate.id.opaque.split("_")
    if len(parts) < 3 or parts[0] != _UTXO_ID_PREFIX or not parts[1]:
        return None
    try:
        commitment = bytes.fromhex(parts[-1])
        if len(commitment) != _COMMITMENT_LEN:
            return None
        parsed = StealthOutputBody.from_json(cast("dict[str, Any]", body))
    except (TypeError, ValueError, KeyError):
        return None
    return commitment, parsed
