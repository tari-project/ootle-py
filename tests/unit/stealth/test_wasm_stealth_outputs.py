"""Real-WASM stealth provider: output statements, balance proof, validation."""

from __future__ import annotations

import json

import pytest

from ootle._crypto._stealth_provider import StealthOutputsStatementResult
from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle._types.address import Address, ResourceAddress
from ootle._types.network import Network
from ootle._types.stealth import (
    BalanceProofSignature,
    Mask,
    Output,
    StealthInputsStatement,
    StealthTransferStatement,
)
from ootle.errors import CryptoBridgeError

from ._wasm_witness import output_witness, outputs_statement

_RESOURCE = ResourceAddress("resource_" + "01" * 32)


def _make_output(
    provider: WasmCryptoProvider,
    amount: int,
    *,
    pay_to: dict[str, object] | None = None,
) -> Output:
    owner_sk, view_sk = provider.generate_ootle_secret_key()
    owner_pk, view_pk = provider.ootle_public_key_from_secret(owner_sk, view_sk)
    dest = Address.from_keys(owner_pk, view_pk, Network.LOCAL_NET, crypto=provider)
    if pay_to is None:
        return Output(destination=dest, amount=amount, resource_address=_RESOURCE)
    return Output(destination=dest, amount=amount, resource_address=_RESOURCE, pay_to=pay_to)


def _single_witness(provider: WasmCryptoProvider, amount: int) -> StealthOutputsStatementResult:
    mask, _ = provider.generate_keypair()
    _, nonce = provider.generate_keypair()
    _, spend = provider.generate_keypair()
    witness = output_witness(mask=mask, sender_nonce=nonce, spend_pk=spend, amount=amount)
    return outputs_statement(provider, [witness])


def test_generate_outputs_statement_round_trips(provider: WasmCryptoProvider) -> None:
    """A statement built from a real Output validates as a balanced transfer."""
    result = provider.generate_outputs_statement(
        specs=[_make_output(provider, 1000)], revealed_output_amount=0
    )
    assert isinstance(result, StealthOutputsStatementResult)
    assert len(result.statement.outputs) == 1
    assert len(result.output_mask.raw) == 32
    assert result.statement.agg_range_proof  # non-empty bulletproof
    raw = provider.generate_balance_proof_signature(
        input_mask=Mask(bytes(32)),
        output_mask=result.output_mask,
        inputs_statement_json=json.dumps({"inputs": [], "revealed_amount": 1000}),
        outputs_statement_json=json.dumps(result.statement.to_json()),
    )
    transfer = StealthTransferStatement(
        inputs_statement=StealthInputsStatement.new_revealed_only(1000),
        outputs_statement=result.statement,
        balance_proof=BalanceProofSignature(public_nonce=raw[:32], signature=raw[32:]),
    )
    provider.validate_transfer(transfer)


def test_generate_outputs_statement_empty(provider: WasmCryptoProvider) -> None:
    result = provider.generate_outputs_statement(specs=(), revealed_output_amount=100)
    assert result.statement.outputs == ()
    assert result.statement.revealed_output_amount == 100


def test_generate_outputs_statement_honours_access_rule(provider: WasmCryptoProvider) -> None:
    output = _make_output(provider, 500, pay_to={"AccessRule": "AllowAll"})
    result = provider.generate_outputs_statement(specs=[output], revealed_output_amount=0)
    assert result.statement.outputs[0].spend_condition == {"AccessRule": "AllowAll"}


def test_outputs_statement_aggregates_single_witness(provider: WasmCryptoProvider) -> None:
    mask, _ = provider.generate_keypair()
    _, nonce = provider.generate_keypair()
    _, spend = provider.generate_keypair()
    result = outputs_statement(
        provider, [output_witness(mask=mask, sender_nonce=nonce, spend_pk=spend, amount=1000)]
    )
    assert isinstance(result, StealthOutputsStatementResult)
    # The aggregate of a single witness mask is that mask.
    assert result.output_mask == Mask(mask)
    assert len(result.statement.outputs) == 1
    assert result.statement.agg_range_proof  # non-empty bulletproof


def test_generate_balance_proof_signature_returns_64_bytes(
    provider: WasmCryptoProvider,
) -> None:
    result = _single_witness(provider, 1000)
    sig = provider.generate_balance_proof_signature(
        input_mask=Mask(bytes(32)),
        output_mask=result.output_mask,
        inputs_statement_json=json.dumps({"inputs": [], "revealed_amount": 1000}),
        outputs_statement_json=json.dumps(result.statement.to_json()),
    )
    assert len(sig) == 64


def _build_transfer(
    raw_sig: bytes,
    revealed_input: int,
    result: StealthOutputsStatementResult,
) -> StealthTransferStatement:
    return StealthTransferStatement(
        inputs_statement=StealthInputsStatement.new_revealed_only(revealed_input),
        outputs_statement=result.statement,
        balance_proof=BalanceProofSignature(public_nonce=raw_sig[:32], signature=raw_sig[32:]),
    )


def test_validate_transfer_accepts_valid_rejects_tampered(
    provider: WasmCryptoProvider,
) -> None:
    result = _single_witness(provider, 1000)
    raw_sig = provider.generate_balance_proof_signature(
        input_mask=Mask(bytes(32)),
        output_mask=result.output_mask,
        inputs_statement_json=json.dumps({"inputs": [], "revealed_amount": 1000}),
        outputs_statement_json=json.dumps(result.statement.to_json()),
    )
    provider.validate_transfer(_build_transfer(raw_sig, 1000, result))

    # Tampering with the revealed amount breaks the balance proof.
    with pytest.raises(CryptoBridgeError):
        provider.validate_transfer(_build_transfer(raw_sig, 999, result))
