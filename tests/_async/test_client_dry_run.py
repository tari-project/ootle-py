"""``send_dry_run`` — HTTP mock tests."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle import AsyncOotleClient, LocalSigner, OotleSecretKey, OotleWallet
from ootle._async._send import mark_dry_run
from ootle._types.network import Network
from ootle._types.transaction import TransactionRequest, UnsignedTransaction
from ootle.errors import InvalidArgumentError

from ._helpers import network_response

_NETWORK = network_response()


def _wallet() -> OotleWallet:
    return OotleWallet(LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)))


def _unsigned_tx(network: int = 0x10, *, dry_run: bool = False) -> UnsignedTransaction:
    payload: dict[str, object] = {
        "network": network,
        "fee_instructions": [],
        "instructions": [],
        "inputs": [],
        "min_epoch": None,
        "max_epoch": None,
        "is_seal_signer_authorized": True,
        "dry_run": dry_run,
    }
    return UnsignedTransaction(json=json.dumps(payload))


def _dry_run_response(fee: int = 500) -> dict[str, object]:
    # Mirrors the engine ``ExecuteResult`` JSON the indexer returns.
    return {
        "transaction_id": "deadbeef" * 8,
        "result": {
            "finalize": {
                "result": {"Accept": {"up_substates": [], "down_substates": []}},
                "events": [],
                "logs": [],
                "fee_receipt": {
                    "total_fee_payment": fee,
                    "total_fees_paid": fee,
                    "total_fee_overcharge": 0,
                    "cost_breakdown": {"breakdown": {"RuntimeCall": fee}},
                },
            },
            "execution_time": {"secs": 0, "nanos": 1},
            "execute_epoch": 3,
        },
    }


async def test_send_dry_run_returns_dry_run_result(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    httpx_mock.add_response(url="http://idx/transactions/dry-run", json=_dry_run_response(750))
    async with AsyncOotleClient.connect("http://idx", wallet=_wallet()) as client:
        result = await client.send_dry_run(_unsigned_tx())
    assert result.estimated_fee == 750


async def test_send_dry_run_outcome_commit(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    httpx_mock.add_response(url="http://idx/transactions/dry-run", json=_dry_run_response())
    async with AsyncOotleClient.connect("http://idx", wallet=_wallet()) as client:
        result = await client.send_dry_run(_unsigned_tx())
    assert result.outcome is not None
    assert result.outcome.is_commit


async def test_send_dry_run_without_wallet_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=_NETWORK)
    async with AsyncOotleClient.connect("http://idx") as client:
        with pytest.raises(InvalidArgumentError):
            await client.send_dry_run(_unsigned_tx())


def test_mark_dry_run_forces_flag_on_unsigned() -> None:
    out = mark_dry_run(_unsigned_tx(dry_run=False))
    assert isinstance(out, UnsignedTransaction)
    assert json.loads(out.json)["dry_run"] is True


def test_mark_dry_run_forces_flag_on_request_transaction() -> None:
    out = mark_dry_run(TransactionRequest(transaction=_unsigned_tx(dry_run=False)))
    assert isinstance(out, TransactionRequest)
    assert out.transaction is not None
    assert json.loads(out.transaction.json)["dry_run"] is True


def test_mark_dry_run_passes_through_empty_request() -> None:
    request = TransactionRequest()
    assert mark_dry_run(request) is request
