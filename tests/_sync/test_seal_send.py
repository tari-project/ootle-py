"""``client.seal_transaction`` + ``client.send_transaction`` tests."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

import ootle._sync._watcher._actor as actor_mod
from ootle import (
    OotleClient,
    LocalSigner,
    OotleSecretKey,
    OotleWallet,
    Transaction,
    TransactionRequest,
    UnsignedTransaction,
)
from ootle._types.network import Network
from ootle.errors import InvalidArgumentError
from tests._helpers.crypto import MockCryptoProvider
from tests._helpers.sse import fake_connect_sse

from ._helpers import network_response


def _wallet() -> OotleWallet:
    return OotleWallet(LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)))


def _stub_events_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in a quiet ``/events`` SSE source so ``send_transaction`` does no real I/O."""

    def _open(*_a: object, **_k: object) -> object:
        return fake_connect_sse([], keep_open=True)

    monkeypatch.setattr(actor_mod, "_open_sse_stream", _open)


def test_seal_unsigned_transaction(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet(), crypto=MockCryptoProvider()) as client:
        unsigned = UnsignedTransaction(json="{}")
        sealed = client.seal_transaction(unsigned)
    assert isinstance(sealed, Transaction)
    assert "sealed" in sealed.json


def test_seal_request_without_transaction_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet(), crypto=MockCryptoProvider()) as client:
        with pytest.raises(InvalidArgumentError):
            client.seal_transaction(TransactionRequest())


def test_seal_without_wallet_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", crypto=MockCryptoProvider()) as client:
        with pytest.raises(InvalidArgumentError):
            client.seal_transaction(UnsignedTransaction(json="{}"))


def test_send_transaction_returns_pending_handle(
    httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_events_stream(monkeypatch)
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    httpx_mock.add_response(
        url="http://idx/transactions", method="POST", json={"transaction_id": "tx_xyz"}
    )
    with OotleClient.connect("http://idx", wallet=_wallet(), crypto=MockCryptoProvider()) as client:
        sealed = Transaction(json="{}")
        pending = client.send_transaction(sealed)
    assert pending.tx_id == "tx_xyz"
    posts = [r for r in httpx_mock.get_requests() if r.url.path == "/transactions"]
    assert len(posts) == 1
    body = posts[0].read().decode()
    assert "envelope" not in body  # the mock returns a hex digest, not the literal "envelope"
    assert "transaction" in body
