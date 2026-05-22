"""Mixin: real stealth-method implementations driving the WASM blob.

Replaces the old ``WasmStealthStubsMixin`` (every method raised
``NotImplementedError``). :class:`WasmStealthMethodsMixin` composes the
statement-side methods (:class:`~ootle._crypto._wasm_stealth_outputs.WasmStealthOutputsMixin`)
with the DH / unblind / mask-aggregation methods defined here, so
:class:`~ootle._crypto._wasm_provider.WasmCryptoProvider` satisfies the
:class:`~ootle._crypto._stealth_provider.StealthCryptoProvider`
Protocol natively.

Each method mirrors the call shape of the transfer-path methods on
``WasmCryptoProvider``: take the store lock, allocate inputs, call the
export, unwrap, return a typed dataclass. The store lock serialises every
call (``wasmtime.Store`` is not thread-safe).

Every method is a plain ``def`` (the WASM work is synchronous behind the
lock — there is nothing to ``await``), matching ``aggregate_input_masks``.
``_crypto/`` is not ``unasync``-mirrored — this one shared provider is
imported by both the async source and the generated ``_sync/`` mirror, so a
single synchronous surface is the only shape that works for both. The
``_async/`` callers offload these blocking calls onto a worker thread; the
``_sync/`` callers invoke them directly.

Every stealth Protocol method drives a real export, including
``generate_outputs_statement`` (via ``createStealthOutputWitness``) — see
:class:`WasmStealthOutputsMixin`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle._crypto._bridge import _abi
from ootle._crypto._wasm_results import open_box, take_box_result, take_bytes_result
from ootle._crypto._wasm_stealth_helpers import parse_output_body
from ootle._crypto._wasm_stealth_outputs import WasmStealthOutputsMixin
from ootle._types.stealth import DecryptedData, Mask

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._crypto._bridge import Bridge


class WasmStealthMethodsMixin(WasmStealthOutputsMixin):
    """Every stealth Protocol method, backed by the vendored WASM blob."""

    _bridge: Bridge  # supplied by WasmCryptoProvider

    def unblind_output(
        self,
        commitment: bytes,
        output_body_json: str,
        view_secret: bytes,
        skip_memo: bool,
    ) -> DecryptedData:
        sender_nonce, encrypted_data = parse_output_body(output_body_json)
        b = self._bridge
        with b.lock:
            vp, vl = _abi.alloc_bytes(b, view_secret)
            np_, nl = _abi.alloc_bytes(b, sender_nonce)
            ret = b.exports["encryptedDataDhKdfAead"](b.store, vp, vl, np_, nl)
            enc_key = take_bytes_result(b, ret, context="unblind_output")
            cp, cl = _abi.alloc_bytes(b, commitment)
            ep, el = _abi.alloc_bytes(b, encrypted_data)
            kp, kl = _abi.alloc_bytes(b, enc_key)
            ret = b.exports["unblindOutput"](b.store, cp, cl, ep, el, kp, kl, 1 if skip_memo else 0)
            box = take_box_result(b, ret, context="unblind_output")
            with open_box(b, box, "__wbg_decryptedoutputresult_free") as acc:
                mask = acc.read_bytes("__wbg_get_decryptedoutputresult_mask")
                value = acc.read_int("__wbg_get_decryptedoutputresult_value")
                memo_json = acc.read_optional_str("__wbg_get_decryptedoutputresult_memo_json")
        # The blob returns the memo as JSON (a serialised ``Memo`` enum); we
        # carry it as UTF-8 bytes. The only production caller passes
        # skip_memo=True, so memo is None on the spend path.
        memo = None if memo_json is None else memo_json.encode("utf-8")
        return DecryptedData(mask=mask, value=value, memo=memo)

    def aggregate_input_masks(self, masks: Sequence[Mask]) -> Mask:
        concat = b"".join(m.raw for m in masks)
        b = self._bridge
        with b.lock:
            mp, ml = _abi.alloc_bytes(b, concat)
            ret = b.exports["aggregateInputMasks"](b.store, mp, ml)
            agg = take_bytes_result(b, ret, context="aggregate_input_masks")
        return Mask(agg)

    def stealth_dh_secret(
        self,
        network_byte: int,
        owner_secret: bytes,
        public_nonce: bytes,
    ) -> bytes:
        b = self._bridge
        with b.lock:
            sp, sl = _abi.alloc_bytes(b, owner_secret)
            np_, nl = _abi.alloc_bytes(b, public_nonce)
            ret = b.exports["stealthDhSecret"](b.store, network_byte, sp, sl, np_, nl)
            return take_bytes_result(b, ret, context="stealth_dh_secret")
