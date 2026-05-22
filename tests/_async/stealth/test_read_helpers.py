"""Client / wallet stealth read helpers — real WASM provider.

Exercises the AEAD owner-read end to end: ``decrypt_owned_utxo`` and
``OotleWallet.decrypt_input_data`` recover ``(value, mask)`` from an output's
``encrypted_data`` using the recorded unblind vector (the blob ships no encrypt
export). The remaining tests cover ``generate_outputs_statement`` and the
non-stealth ``crypto=`` provider guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from ootle import LocalSigner, OotleSecretKey, OotleWallet
from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle._types.network import Network
from ootle._types.stealth import EncryptedData, Output
from ootle._types.substate import Substate, SubstateId, UnknownSubstateValue
from ootle.errors import InvalidArgumentError

from ._builder_helpers import RESOURCE, make_client, recipient_address

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


def _engine_utxo_substate(
    commitment_hex: str,
    public_nonce_hex: str = "ff" * 32,
    encrypted_hex: str = "00" * 80,
) -> Substate:
    """Engine ``Utxo`` substate shape (``OutputBody``: ``public_nonce``, no commitment)."""
    body: dict[str, Any] = {
        "public_nonce": public_nonce_hex,
        "encrypted_data": encrypted_hex,
        "minimum_value_promise": 0,
        "viewable_balance": None,
    }
    inner = {"output": body, "spend_condition": {"Signed": "ff" * 32}, "tag": 1}
    return Substate(
        id=SubstateId(opaque=f"utxo_resource_{commitment_hex}"),
        version=0,
        value=UnknownSubstateValue(
            discriminator="Utxo", raw={"Utxo": {"output": inner, "is_frozen": False}}
        ),
    )


async def test_decrypt_owned_utxo_decodes_engine_substate(
    httpx_mock: HTTPXMock, stealth_unblind_vector: dict[str, Any]
) -> None:
    """AEAD owner-read parses the engine substate (commitment from id) and decrypts.

    Regression for the read path parsing the send-side ``UnspentOutput`` shape
    instead of the engine ``OutputBody`` — recipients decoded ``Amount(0)``.
    """
    vec = stealth_unblind_vector
    client = await make_client(httpx_mock, crypto=WasmCryptoProvider.load_default())
    utxo = _engine_utxo_substate(
        vec["commitment"], vec["sender_public_nonce"], vec["encrypted_data"]
    )
    decrypted = await client.decrypt_owned_utxo(bytes.fromhex(vec["view_secret"]), utxo)
    assert decrypted is not None
    assert decrypted.value == vec["value"]
    assert decrypted.mask.hex() == vec["mask"]
    await client.aclose()


async def test_decrypt_owned_utxo_returns_none_for_non_utxo(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    sub = Substate(
        id=SubstateId(opaque="component_" + "00" * 32),
        version=0,
        value=UnknownSubstateValue(discriminator="Component", raw={"Component": {}}),
    )
    assert await client.decrypt_owned_utxo(b"\x11" * 32, sub) is None
    await client.aclose()


async def test_read_helpers_reject_non_stealth_crypto(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock, crypto=object())
    utxo = _engine_utxo_substate("dd" * 32)
    with pytest.raises(InvalidArgumentError):
        await client.decrypt_owned_utxo(b"\x55" * 32, utxo)
    await client.aclose()


def test_wallet_decrypt_input_data_routes_to_provider(
    stealth_unblind_vector: dict[str, Any],
) -> None:
    vec = stealth_unblind_vector
    wallet = OotleWallet(
        LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)),
        crypto=WasmCryptoProvider.load_default(),
    )
    decrypted = wallet.decrypt_input_data(
        commitment=bytes.fromhex(vec["commitment"]),
        encrypted_input=EncryptedData(raw=bytes.fromhex(vec["encrypted_data"])),
        sender_public_nonce=bytes.fromhex(vec["sender_public_nonce"]),
        view_secret=bytes.fromhex(vec["view_secret"]),
        skip_memo=True,
    )
    assert decrypted.value == vec["value"]
    assert decrypted.mask.hex() == vec["mask"]


def test_wallet_generate_outputs_statement_routes_to_provider() -> None:
    """Wallet helper delegates to the real WASM stealth provider."""
    wallet = OotleWallet(
        LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)),
        crypto=WasmCryptoProvider.load_default(),
    )
    out = wallet.generate_outputs_statement([], revealed=500)
    assert out.outputs_statement.revealed_output_amount == 500


def test_wallet_generate_outputs_statement_signs_balance_proof() -> None:
    """A stealth output yields a complete statement: balance proof + derived revealed input.

    Regression for the faucet stealth path submitting ``balance_proof=None``,
    which the engine rejects ("Balance proof must be provided and public nonce
    and signature cannot be zero"). The revealed input must also cover every
    output so the transfer balances.
    """
    wallet = OotleWallet(
        LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)),
        crypto=WasmCryptoProvider.load_default(),
    )
    fee, stealth_amount = 500, 2_000
    statement = wallet.generate_outputs_statement(
        [Output(destination=recipient_address(), amount=stealth_amount, resource_address=RESOURCE)],
        revealed=fee,
    )
    assert statement.balance_proof is not None
    assert statement.balance_proof.public_nonce != b"\x00" * 32
    assert statement.balance_proof.signature != b"\x00" * 32
    assert statement.inputs_statement.revealed_amount == stealth_amount + fee
    assert statement.outputs_statement.revealed_output_amount == fee


def test_wallet_read_helpers_reject_non_stealth_crypto() -> None:
    wallet = OotleWallet(LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)), crypto=object())
    with pytest.raises(InvalidArgumentError):
        wallet.decrypt_input_data(
            commitment=b"\x00" * 32,
            encrypted_input=EncryptedData.empty(),
            sender_public_nonce=b"\x00" * 32,
            view_secret=b"\x00" * 32,
        )
