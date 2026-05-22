"""Pure marshalling helpers for :class:`WasmStealthMethodsMixin`.

Split out of :mod:`ootle._crypto._wasm_stealth` so the mixin stays under
the 200-line ceiling. These functions touch no WASM state — they only
translate between :mod:`ootle._types.stealth` shapes and the flat byte
arguments the stealth exports consume.
"""

from __future__ import annotations

import json
from typing import Any, cast

from ootle._types.stealth import UnspentOutput
from ootle.errors import InvalidArgumentError


def parse_output_body(output_body_json: str) -> tuple[bytes, bytes]:
    """Pull ``(sender_public_nonce, encrypted_data)`` out of a UTXO body.

    Accepts either a :class:`~ootle._types.stealth.StealthUnspentOutput`
    envelope (the shape the authorizer ships — the body lives under an
    ``"output"`` key) or a bare :class:`UnspentOutput` body.

    Args:
        output_body_json: JSON-encoded UTXO body.

    Returns:
        The 32-byte sender public nonce and the raw encrypted-data bytes.
    """
    decoded: Any = json.loads(output_body_json)
    if not isinstance(decoded, dict):
        msg = "output body JSON must be an object"
        raise InvalidArgumentError(msg)
    body = cast("dict[str, Any]", decoded)
    inner = body["output"] if isinstance(body.get("output"), dict) else body
    output = UnspentOutput.from_json(cast("dict[str, Any]", inner))
    return output.sender_public_nonce, output.encrypted_data.raw
