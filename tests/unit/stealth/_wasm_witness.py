"""Helpers for the real-WASM stealth provider tests.

Builds output-witness JSON and drives the WASM outputs-statement export so
the statement and transfer-validation tests can construct their inputs
entirely from the vendored blob — no network, no fixtures.

``encrypted_data`` is zeroed: ``generateStealthOutputsStatement`` treats it
as opaque passthrough (it never decrypts), so the produced statements are
structurally valid and pass ``validateStealthTransfer``. The commitments
and ElGamal proofs the export computes are real.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ootle._crypto._stealth_provider import StealthOutputsStatementResult
    from ootle._crypto._wasm_provider import WasmCryptoProvider

ZERO_ENCRYPTED: str = "00" * 80


def output_witness(
    *,
    mask: bytes,
    sender_nonce: bytes,
    spend_pk: bytes,
    amount: int,
    view_public_key: bytes | None = None,
) -> dict[str, Any]:
    """Build one ``StealthOutputWitness`` JSON record (zeroed encrypted data)."""
    witness: dict[str, Any] = {
        "amount": amount,
        "mask": mask.hex(),
        "sender_public_nonce": sender_nonce.hex(),
        "minimum_value_promise": 0,
        "encrypted_data": ZERO_ENCRYPTED,
    }
    if view_public_key is not None:
        witness["resource_view_key"] = view_public_key.hex()
    return {"witness": witness, "spend_condition": {"Signed": spend_pk.hex()}, "tag": 0}


def outputs_statement(
    provider: WasmCryptoProvider,
    witnesses: list[dict[str, Any]],
    revealed_output_amount: int = 0,
) -> StealthOutputsStatementResult:
    """Run ``generateStealthOutputsStatement`` over ready-made witnesses."""
    return provider._outputs_statement_from_witnesses(  # pyright: ignore[reportPrivateUsage]  # internal access
        json.dumps(witnesses), revealed_output_amount
    )
