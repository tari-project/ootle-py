"""``IndexerTransport`` — submit / dry-run / get-result / receipt endpoints."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from ootle._sync._transport import IndexerTransport
from ootle._types.transaction import TransactionId


def test_submit_transaction_round_trips(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/transactions",
        method="POST",
        json={"transaction_id": "abcd1234"},
    )
    with IndexerTransport("http://idx") as transport:
        tx_id = transport.submit_transaction("envelope_b64==")
    assert tx_id == "abcd1234"


def test_submit_dry_run_returns_dry_run_result(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/transactions/dry-run",
        method="POST",
        json={"transaction_id": "abcd", "result": {"finalize": {"result": "Accept"}}},
    )
    with IndexerTransport("http://idx") as transport:
        result = transport.submit_transaction_dry_run("env==")
    assert result.transaction_id == "abcd"
    assert "finalize" in result.raw


def test_get_transaction_result_pending(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/transactions/aabb/result",
        json={"result": "Pending"},
    )
    with IndexerTransport("http://idx") as transport:
        is_finalized, outcome = transport.get_transaction_result(TransactionId("aabb"))
    assert is_finalized is False
    assert outcome is None


def test_get_transaction_result_committed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/transactions/aabb/result",
        json={
            "result": {
                "Finalized": {
                    "final_decision": "Commit",
                    "execution_result": None,
                    "abort_details": None,
                }
            }
        },
    )
    with IndexerTransport("http://idx") as transport:
        is_finalized, outcome = transport.get_transaction_result(TransactionId("aabb"))
    assert is_finalized is True
    assert outcome is not None
    assert outcome.is_commit


def test_get_transaction_receipt_404_returns_none(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/transaction-receipts/aabb", status_code=404)
    with IndexerTransport("http://idx") as transport:
        receipt = transport.get_transaction_receipt(TransactionId("aabb"))
    assert receipt is None


def test_get_transaction_result_and_receipt_escape_tx_id(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/transactions/aa%2F..%3Fx%3D1/result",
        json={"result": "Pending"},
    )
    httpx_mock.add_response(
        url="http://idx/transaction-receipts/aa%2F..%3Fx%3D1",
        status_code=404,
    )
    raw_id = TransactionId("aa/..?x=1")
    with IndexerTransport("http://idx") as transport:
        is_finalized, outcome = transport.get_transaction_result(raw_id)
        receipt = transport.get_transaction_receipt(raw_id)
    assert is_finalized is False
    assert outcome is None
    assert receipt is None
