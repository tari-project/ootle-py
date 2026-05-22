"""``StealthTransfer`` + ``WalletStealthAuthorizer`` — sync surface, real WASM.

Hand-written sync counterpart of the async builder/authorizer suites.
Exercises the synchronous stealth crypto path end to end through
:class:`~ootle.OotleClient`:

- ``generate_outputs_statement`` (builder prepare),
- ``unblind_output`` + ``aggregate_input_masks`` (authorizer input fetch),
- ``generate_balance_proof_signature`` + ``validate_transfer`` (authorizer).

These all returned un-awaited coroutines on the sync client before the
crypto provider was made synchronous.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from ootle._sync.stealth.authorizer import WalletStealthAuthorizer
from ootle._sync.stealth.transfer import StealthTransfer
from ootle._types.stealth import Output, StealthOutputsStatement, StealthTransferStatement
from ootle._types.transaction import UnsignedTransaction
from ootle.errors import InvalidArgumentError
from tests._helpers.instructions import kinds_and_methods

from ._builder_helpers import COMPONENT, RESOURCE, make_client, recipient_address

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


def test_prepare_deposits_revealed_output_and_folds_fee(httpx_mock: HTTPXMock) -> None:
    """Fee folds into the revealed output; the bucket is deposited back (Model B)."""
    client = make_client(httpx_mock)
    spec = (
        StealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 110)
        .to_revealed_output(100)
        .pay_fee_from_revealed(10)
        .prepare()
    )
    assert spec.statement.outputs_statement.revealed_output_amount == 110
    body: dict[str, Any] = json.loads(spec.unsigned.json)
    instructions: list[Any] = body["instructions"]
    kinds, methods = kinds_and_methods(instructions)
    assert "StealthTransfer" in kinds
    assert body["fee_instructions"]
    assert "deposit" in methods
    st_idx = kinds.index("StealthTransfer")
    assert "PutLastInstructionOutputOnWorkspace" in kinds[st_idx + 1 :]
    client.close()


def test_prepare_must_sign_when_fee_from_revealed_without_revealed_input(
    httpx_mock: HTTPXMock,
) -> None:
    """``pay_fee_from_revealed`` draws on the account, so the account key must sign."""
    client = make_client(httpx_mock)
    addr = recipient_address()
    spec = (
        StealthTransfer(client, RESOURCE)
        .spend_stealth_input(addr, b"\xaa" * 32)
        .to_stealth_output(Output(destination=addr, amount=50, resource_address=RESOURCE))
        .pay_fee_from_revealed(10)
        .prepare()
    )
    assert spec.signature_requirements.must_sign_with_account_key()
    client.close()


def test_second_spend_revealed_input_raises(httpx_mock: HTTPXMock) -> None:
    """A stealth transfer has a single revealed-input slot; a second call is rejected."""
    client = make_client(httpx_mock)
    b = StealthTransfer(client, RESOURCE).spend_revealed_input(COMPONENT, 100)
    with pytest.raises(InvalidArgumentError):
        b.spend_revealed_input(COMPONENT, 50)
    instrs = json.loads(b._builder.build_unsigned().json)["instructions"]  # pyright: ignore[reportPrivateUsage]  # internal access
    puts = [i for i in instrs if "PutLastInstructionOutputOnWorkspace" in i]
    assert len(puts) == 1
    client.close()


def test_prepare_with_stealth_output_uses_provider_statement(httpx_mock: HTTPXMock) -> None:
    client = make_client(httpx_mock)
    out = Output(destination=recipient_address(), amount=42, resource_address=RESOURCE)
    spec = (
        StealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 42)
        .to_stealth_output(out)
        .prepare()
    )
    assert isinstance(spec.statement.outputs_statement, StealthOutputsStatement)
    assert spec.statement.outputs_statement.outputs
    client.close()


def test_authorizer_revealed_only_validates_without_balance_proof(httpx_mock: HTTPXMock) -> None:
    """Revealed-only transfer carries no balance proof; real-WASM validate accepts it."""
    client = make_client(httpx_mock)
    spec = (
        StealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 100)
        .to_revealed_output(100)
        .prepare()
    )
    assert client.wallet is not None
    auth = WalletStealthAuthorizer.from_spec(client.wallet, spec)
    new_spec = auth.prepare(client)
    assert new_spec.statement.balance_proof is None
    client.close()


def test_authorizer_revealed_in_stealth_out_signs_and_validates(httpx_mock: HTTPXMock) -> None:
    """A balanced revealed-in → stealth-out transfer gets a real, validatable balance proof."""
    client = make_client(httpx_mock)
    out = Output(destination=recipient_address(), amount=1000, resource_address=RESOURCE)
    spec = (
        StealthTransfer(client, RESOURCE)
        .spend_revealed_input(COMPONENT, 1000)
        .to_stealth_output(out)
        .prepare()
    )
    assert client.wallet is not None
    auth = WalletStealthAuthorizer.from_spec(client.wallet, spec)
    new_spec = auth.prepare(client)
    proof = new_spec.statement.balance_proof
    assert proof is not None
    assert len(proof.public_nonce) == 32
    assert len(proof.signature) == 32
    client.close()


def test_authorizer_with_non_stealth_crypto_raises(httpx_mock: HTTPXMock) -> None:
    client = make_client(httpx_mock, crypto=object())
    assert client.wallet is not None
    auth = WalletStealthAuthorizer(client.wallet, _fake_spec())
    with pytest.raises(InvalidArgumentError):
        auth.prepare(client)
    client.close()


def test_prepare_rejects_unexpected_provider_result_shape(httpx_mock: HTTPXMock) -> None:
    """A provider returning a non-result from the now-sync call is rejected, not awaited."""

    class _BadCrypto:
        def generate_outputs_statement(self, _specs: object, _revealed: int) -> object:
            return "not a result"

    client = make_client(httpx_mock, crypto=_BadCrypto())
    b = StealthTransfer(client, RESOURCE).spend_revealed_input(COMPONENT, 1).to_revealed_output(1)
    with pytest.raises(InvalidArgumentError):
        b.prepare()
    client.close()


def _fake_spec() -> Any:
    """Build a minimal :class:`StealthTransferSpec` for the guard path."""
    from ootle._sync.stealth._builder_helpers import StealthTransferState  # noqa: PLC0415
    from ootle._sync.stealth._spec import StealthTransferSpec  # noqa: PLC0415
    from ootle._types.stealth.requirements import SignatureRequirements  # noqa: PLC0415

    statement = StealthTransferStatement.revealed_only(1, 1)
    state = StealthTransferState(
        resource=RESOURCE, revealed_input_amount=1, revealed_output_amount=1
    )
    return StealthTransferSpec(
        unsigned=UnsignedTransaction(json=json.dumps({"instructions": []})),
        statement=statement,
        signature_requirements=SignatureRequirements.new_must_sign_with_account_key(()),
        output_mask=None,
        state=state,
    )
