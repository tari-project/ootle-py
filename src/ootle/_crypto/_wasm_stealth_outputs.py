"""Statement-side stealth methods for the WASM provider.

Holds the output-statement, balance-proof, and transfer-validation
methods. Split from :mod:`ootle._crypto._wasm_stealth` (which composes
this with the DH / unblind / mask-aggregation half) to stay under the
200-line ceiling.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from ootle._crypto._bridge import _abi
from ootle._crypto._stealth_provider import StealthOutputsStatementResult
from ootle._crypto._wasm_results import (
    open_box,
    take_box_result,
    take_str_result,
    take_unit_result,
)
from ootle._types.stealth import Mask, StealthOutputsStatement
from ootle.errors import CryptoBridgeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._crypto._bridge import Bridge
    from ootle._types.stealth import Output, StealthTransferStatement


def _pay_to_json(pay_to: dict[str, Any]) -> str | None:
    """Map the Python ``pay_to`` dict to the Rust ``PayTo`` JSON the export expects.

    Rust ``PayTo`` is the unit string ``"StealthPublicKey"`` (the default) or
    ``{"AccessRule": <rule>}``. The Python default ``{"StealthPublicKey": {}}``
    maps to the unit variant — passed as ``None`` so the export uses its default.
    """
    if "AccessRule" in pay_to:
        return json.dumps(pay_to, separators=(",", ":"))
    return None


class WasmStealthOutputsMixin:
    """Output-statement, balance-proof, and validation stealth methods."""

    _bridge: Bridge  # supplied by WasmCryptoProvider

    def generate_outputs_statement(
        self,
        specs: Sequence[Output],
        revealed_output_amount: int,
    ) -> StealthOutputsStatementResult:
        witnesses = [self._create_output_witness(spec) for spec in specs]
        witnesses_json = "[" + ",".join(witnesses) + "]"
        return self._outputs_statement_from_witnesses(witnesses_json, revealed_output_amount)

    def _create_output_witness(self, output: Output) -> str:
        """Marshal one :class:`Output` into a witness JSON via ``createStealthOutputWitness``.

        Mask, ephemeral nonce, AEAD encryption, spend condition, and tag are all
        generated inside the blob; the destination keys + network come from the
        already-decoded :class:`~ootle._types.address.Address`.
        """
        dest = output.destination
        memo = None if output.memo is None else json.dumps(output.memo, separators=(",", ":"))
        pay_to = _pay_to_json(output.pay_to)
        b = self._bridge
        with b.lock:
            ap, al = _abi.alloc_bytes(b, dest.owner_pk)
            vp, vl = _abi.alloc_bytes(b, dest.view_pk)
            rp, rl = _abi.alloc_str(b, str(output.resource_address))
            kp, kl = _abi.alloc_optional_bytes(b, output.resource_view_key)
            mp, ml = (0, 0) if memo is None else _abi.alloc_str(b, memo)
            pp, pl = (0, 0) if pay_to is None else _abi.alloc_str(b, pay_to)
            ret = b.exports["createStealthOutputWitness"](
                b.store,
                dest.network.value,
                ap,
                al,
                vp,
                vl,
                output.amount,
                rp,
                rl,
                kp,
                kl,
                mp,
                ml,
                pp,
                pl,
                output.minimum_value_promise,
            )
            return take_str_result(b, ret, context="generate_outputs_statement")

    def _outputs_statement_from_witnesses(
        self,
        witnesses_json: str,
        revealed_output_amount: int,
    ) -> StealthOutputsStatementResult:
        """Drive ``generateStealthOutputsStatement`` from ready-made witnesses.

        The WASM back-half of :meth:`generate_outputs_statement`: it takes
        the witness-array JSON the per-output front-half produced and
        returns the aggregated statement plus output mask.
        """
        b = self._bridge
        with b.lock:
            jp, jl = _abi.alloc_str(b, witnesses_json)
            ret = b.exports["generateStealthOutputsStatement"](
                b.store, jp, jl, revealed_output_amount
            )
            box = take_box_result(b, ret, context="generate_outputs_statement")
            with open_box(b, box, "__wbg_stealthoutputsresult_free") as acc:
                stmt = acc.read_optional_str("__wbg_get_stealthoutputsresult_statement_json")
                agg = acc.read_bytes("__wbg_get_stealthoutputsresult_aggregated_output_mask")
        if stmt is None:
            msg = "generateStealthOutputsStatement returned no statement"
            raise CryptoBridgeError(msg, context="generate_outputs_statement")
        statement = StealthOutputsStatement.from_json(cast("dict[str, Any]", json.loads(stmt)))
        return StealthOutputsStatementResult(statement=statement, output_mask=Mask(agg))

    def generate_balance_proof_signature(
        self,
        input_mask: Mask,
        output_mask: Mask,
        inputs_statement_json: str,
        outputs_statement_json: str,
    ) -> bytes:
        b = self._bridge
        with b.lock:
            ip, il = _abi.alloc_bytes(b, input_mask.raw)
            op, ol = _abi.alloc_bytes(b, output_mask.raw)
            sp, sl = _abi.alloc_str(b, inputs_statement_json)
            tp, tl = _abi.alloc_str(b, outputs_statement_json)
            ret = b.exports["generateStealthBalanceProofSignature"](
                b.store, ip, il, op, ol, sp, sl, tp, tl
            )
            box = take_box_result(b, ret, context="generate_balance_proof_signature")
            with open_box(b, box, "__wbg_schnorrsignatureresult_free") as acc:
                nonce = acc.read_bytes("__wbg_get_schnorrsignatureresult_public_nonce")
                sig = acc.read_bytes("__wbg_get_schnorrsignatureresult_signature")
        return nonce + sig

    def validate_transfer(self, transfer_statement: StealthTransferStatement) -> None:
        # view_key is None: viewable-resource validation needs the resource
        # view public key, which the transfer statement does not carry. The
        # engine performs the authoritative check at submission.
        transfer_json = json.dumps(transfer_statement.to_json(), separators=(",", ":"))
        b = self._bridge
        with b.lock:
            tp, tl = _abi.alloc_str(b, transfer_json)
            vp, vl = _abi.alloc_optional_bytes(b, None)
            ret = b.exports["validateStealthTransfer"](b.store, tp, tl, vp, vl)
            take_unit_result(b, ret, context="validate_transfer")
