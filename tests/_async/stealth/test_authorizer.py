"""``AsyncWalletStealthAuthorizer`` — coverage against a WASM-shaped provider."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pytest_httpx import HTTPXMock

from ootle._async.stealth.authorizer import AsyncWalletStealthAuthorizer
from ootle._async.stealth.transfer import AsyncStealthTransfer
from ootle._types.stealth import (
    BalanceProofSignature,
    Output,
    StealthTransferStatement,
)
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import InvalidArgumentError

from ._builder_helpers import COMPONENT, RESOURCE, make_client, recipient_address


async def test_prepare_revealed_only_skips_balance_proof_but_validates(
    httpx_mock: HTTPXMock,
) -> None:
    """A revealed-only transfer carries no balance proof; real-WASM validate accepts it."""
    client = await make_client(httpx_mock)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .prepare()
    )
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer.from_spec(client.wallet, spec)
    new_spec = await auth.prepare(client)
    # No stealth pieces ⇒ no balance proof; prepare succeeding means the
    # real ``validateStealthTransfer`` export accepted the revealed-only shape.
    assert new_spec.statement.balance_proof is None
    await client.aclose()


async def test_prepare_revealed_in_stealth_out_signs_and_validates(httpx_mock: HTTPXMock) -> None:
    """A balanced revealed-in → stealth-out transfer gets a real, validatable balance proof."""
    client = await make_client(httpx_mock)
    out = Output(destination=recipient_address(), amount=1000, resource_address=RESOURCE)
    spec = await (
        AsyncStealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 1000)
        .to_stealth_output(out)
        .prepare()
    )
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer.from_spec(client.wallet, spec)
    new_spec = await auth.prepare(client)
    # Real ``generateStealthBalanceProofSignature`` + ``validateStealthTransfer``:
    # a 64-byte proof split into a 32-byte nonce + 32-byte signature.
    proof = new_spec.statement.balance_proof
    assert proof is not None
    assert len(proof.public_nonce) == 32
    assert len(proof.signature) == 32
    await client.aclose()


async def test_prepare_with_non_stealth_crypto_raises(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock, crypto=object())
    fake_spec = _fake_spec()
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer(client.wallet, fake_spec)
    with pytest.raises(InvalidArgumentError):
        await auth.prepare(client)
    await client.aclose()


async def test_address_defers_to_wallet_default(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer(client.wallet, _fake_spec())
    assert auth.address() == client.wallet.default_address
    await client.aclose()


async def test_add_signature_returns_unchanged_when_account_key_skipped(
    httpx_mock: HTTPXMock,
) -> None:
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer(
        client.wallet, _fake_spec(), must_sign_with_account_key=False
    )
    body = '{"id":"tx"}'
    assert auth.add_signature(body, b"\x00" * 32, crypto=cast("Any", None)) == body
    await client.aclose()


async def test_add_signature_delegates_to_default_signer(httpx_mock: HTTPXMock) -> None:
    """When the account key must sign, ``add_signature`` forwards to the wallet's default signer."""
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer(client.wallet, _fake_spec())
    out = auth.add_signature('{"id":"tx"}', b"\xaa" * 32, crypto=cast("Any", _StubCrypto()))
    assert "transaction_signer" in out
    await client.aclose()


async def test_seal_delegates_to_default_signer(httpx_mock: HTTPXMock) -> None:
    client = await make_client(httpx_mock)
    assert client.wallet is not None
    auth = AsyncWalletStealthAuthorizer(client.wallet, _fake_spec())
    out = auth.seal('{"id":"tx"}', crypto=cast("Any", _StubCrypto()))
    assert "sealed" in out
    await client.aclose()


def _fake_spec() -> Any:
    """Build a minimal :class:`StealthTransferSpec` for sync/unit-only paths."""
    from ootle._async.stealth._builder_helpers import StealthTransferState  # noqa: PLC0415
    from ootle._async.stealth._spec import StealthTransferSpec  # noqa: PLC0415

    statement = StealthTransferStatement.revealed_only(1, 1)
    state = StealthTransferState(
        resource=RESOURCE, revealed_input_amount=1, revealed_output_amount=1
    )
    return StealthTransferSpec(
        unsigned=UnsignedTransaction(json=json.dumps({"instructions": []})),
        statement=statement,
        signature_requirements=__import__(
            "ootle._types.stealth.requirements", fromlist=["SignatureRequirements"]
        ).SignatureRequirements.new_must_sign_with_account_key(()),
        output_mask=None,
        state=state,
    )


class _StubCrypto:
    """Tiny stand-in for the WASM ``CryptoProvider``."""

    def add_transaction_signer(self, tx_json: str, _sk: bytes, _pk: bytes) -> str:
        return f"{tx_json}|transaction_signer"

    def seal_transaction(self, tx_json: str, _sk: bytes) -> str:
        return f"sealed({tx_json})"


def test_split_balance_proof_bytes_round_trip() -> None:
    from ootle._stealth_balance_proof import split_balance_proof_bytes  # noqa: PLC0415

    raw = bytes(range(64))
    proof = split_balance_proof_bytes(raw)
    assert isinstance(proof, BalanceProofSignature)
    assert proof.public_nonce == raw[:32]
    assert proof.signature == raw[32:]
