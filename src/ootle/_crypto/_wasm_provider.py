"""``WasmCryptoProvider`` — production implementation of :class:`CryptoProvider`.

Each method follows the same shape: lock → write inputs → call export →
unwrap multi-value error → read outputs → free → return. The lock is
required because :class:`wasmtime.Store` is not thread-safe.

The class also inherits :class:`WasmStealthMethodsMixin`, which drives the
blob's stealth exports for every stealth Protocol method, so this
provider natively satisfies both ``CryptoProvider`` and
``StealthCryptoProvider``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._bridge import Bridge, _abi, load_default_bridge
from ._provider import ParsedAddress, SchnorrSignatureResult
from ._wasm_results import (
    open_box,
    take_box_result,
    take_bytes_result,
    take_str_result,
)
from ._wasm_stealth import WasmStealthMethodsMixin


@dataclass(frozen=True, slots=True)
class WasmCryptoProvider(WasmStealthMethodsMixin):
    """Maps the :class:`CryptoProvider` Protocol onto the vendored WASM blob.

    Also satisfies :class:`StealthCryptoProvider` via
    :class:`WasmStealthMethodsMixin`, which drives the blob's stealth
    exports directly — including ``generate_outputs_statement`` (via the
    ``createStealthOutputWitness`` export).
    """

    _bridge: Bridge

    @classmethod
    def load_default(cls) -> WasmCryptoProvider:
        return cls(_bridge=load_default_bridge())

    def generate_keypair(self) -> tuple[bytes, bytes]:
        with self._bridge.lock:
            box_ptr = int(self._bridge.exports["generateKeypair"](self._bridge.store))
            with open_box(self._bridge, box_ptr, "__wbg_keypairresult_free") as box:
                sk = box.read_bytes("__wbg_get_keypairresult_secret_key")
                pk = box.read_bytes("__wbg_get_keypairresult_public_key")
            return sk, pk

    def generate_ootle_secret_key(self) -> tuple[bytes, bytes]:
        with self._bridge.lock:
            box_ptr = int(self._bridge.exports["generateOotleSecretKey"](self._bridge.store))
            with open_box(self._bridge, box_ptr, "__wbg_ootlesecretkey_free") as box:
                owner = box.read_bytes("__wbg_get_ootlesecretkey_owner_key")
                view = box.read_bytes("__wbg_get_ootlesecretkey_view_key")
            return owner, view

    def public_key_from_secret(self, sk: bytes) -> bytes:
        with self._bridge.lock:
            ptr, length = _abi.alloc_bytes(self._bridge, sk)
            ret = self._bridge.exports["publicKeyFromSecretKey"](self._bridge.store, ptr, length)
            return take_bytes_result(self._bridge, ret, context="public_key_from_secret")

    def ootle_public_key_from_secret(self, owner: bytes, view: bytes) -> tuple[bytes, bytes]:
        with self._bridge.lock:
            op, ol = _abi.alloc_bytes(self._bridge, owner)
            vp, vl = _abi.alloc_bytes(self._bridge, view)
            ret = self._bridge.exports["ootlePublicKeyFromSecretKey"](
                self._bridge.store, op, ol, vp, vl
            )
            box_ptr = take_box_result(self._bridge, ret, context="ootle_public_key_from_secret")
            with open_box(self._bridge, box_ptr, "__wbg_ootlepublickey_free") as box:
                o = box.read_bytes("__wbg_get_ootlepublickey_owner_key")
                v = box.read_bytes("__wbg_get_ootlepublickey_view_key")
            return o, v

    def generate_ootle_address(
        self,
        owner_pk: bytes,
        view_pk: bytes,
        network: int,
        memo: bytes | None = None,
    ) -> str:
        with self._bridge.lock:
            op, ol = _abi.alloc_bytes(self._bridge, owner_pk)
            vp, vl = _abi.alloc_bytes(self._bridge, view_pk)
            mp, ml = _abi.alloc_optional_bytes(self._bridge, memo)
            ret = self._bridge.exports["generateOotleAddress"](
                self._bridge.store, op, ol, vp, vl, network, mp, ml
            )
            return take_str_result(self._bridge, ret, context="generate_ootle_address")

    def parse_ootle_address(self, address: str) -> ParsedAddress:
        with self._bridge.lock:
            ptr, length = _abi.alloc_str(self._bridge, address)
            ret = self._bridge.exports["parseOotleAddress"](self._bridge.store, ptr, length)
            box_ptr = take_box_result(self._bridge, ret, context="parse_ootle_address")
            with open_box(self._bridge, box_ptr, "__wbg_parsedootleaddress_free") as box:
                owner = box.read_bytes("__wbg_get_parsedootleaddress_owner_key")
                view = box.read_bytes("__wbg_get_parsedootleaddress_view_key")
                network = box.read_int("__wbg_get_parsedootleaddress_network")
                memo = box.read_optional_bytes("__wbg_get_parsedootleaddress_memo")
            return ParsedAddress(owner_key=owner, view_key=view, network=network, memo=memo)

    def schnorr_sign(self, sk: bytes, message: bytes) -> SchnorrSignatureResult:
        with self._bridge.lock:
            sp, sl = _abi.alloc_bytes(self._bridge, sk)
            mp, ml = _abi.alloc_bytes(self._bridge, message)
            ret = self._bridge.exports["schnorrSign"](self._bridge.store, sp, sl, mp, ml)
            box_ptr = take_box_result(self._bridge, ret, context="schnorr_sign")
            with open_box(self._bridge, box_ptr, "__wbg_schnorrsignatureresult_free") as box:
                nonce = box.read_bytes("__wbg_get_schnorrsignatureresult_public_nonce")
                sig = box.read_bytes("__wbg_get_schnorrsignatureresult_signature")
            return SchnorrSignatureResult(public_nonce=nonce, signature=sig)

    def hash_unsigned_transaction(self, unsigned_json: str, seal_pk: bytes) -> bytes:
        with self._bridge.lock:
            jp, jl = _abi.alloc_str(self._bridge, unsigned_json)
            pp, pl = _abi.alloc_bytes(self._bridge, seal_pk)
            ret = self._bridge.exports["hashUnsignedTransaction"](
                self._bridge.store, jp, jl, pp, pl
            )
            return take_bytes_result(self._bridge, ret, context="hash_unsigned_transaction")

    def add_transaction_signer(self, tx_json: str, signer_sk: bytes, seal_pk: bytes) -> str:
        with self._bridge.lock:
            jp, jl = _abi.alloc_str(self._bridge, tx_json)
            sp, sl = _abi.alloc_bytes(self._bridge, signer_sk)
            pp, pl = _abi.alloc_bytes(self._bridge, seal_pk)
            ret = self._bridge.exports["addTransactionSigner"](
                self._bridge.store, jp, jl, sp, sl, pp, pl
            )
            return take_str_result(self._bridge, ret, context="add_transaction_signer")

    def seal_transaction(self, tx_json: str, seal_sk: bytes) -> str:
        with self._bridge.lock:
            jp, jl = _abi.alloc_str(self._bridge, tx_json)
            sp, sl = _abi.alloc_bytes(self._bridge, seal_sk)
            ret = self._bridge.exports["sealTransaction"](self._bridge.store, jp, jl, sp, sl)
            return take_str_result(self._bridge, ret, context="seal_transaction")

    def bor_encode_transaction(self, transaction_json: str) -> str:
        with self._bridge.lock:
            jp, jl = _abi.alloc_str(self._bridge, transaction_json)
            ret = self._bridge.exports["borEncodeTransaction"](self._bridge.store, jp, jl)
            return take_str_result(self._bridge, ret, context="bor_encode_transaction")
