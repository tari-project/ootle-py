"""``IAccount`` tests — fluent shape + emitted JSON envelope."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle import OotleClient, LocalSigner, OotleSecretKey, OotleWallet
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ResourceAddress
from ootle._types.amount import TARI
from ootle._types.network import Network
from ootle._types.template import TemplateBlob
from ootle.errors import InvalidArgumentError

from ._helpers import network_response

_SOME_RESOURCE = ResourceAddress(
    "resource_0101010101010101010101010101010101010101010101010101010101010101"
)


def _wallet() -> OotleWallet:
    secret = OotleSecretKey.random(Network.LOCAL_NET)
    return OotleWallet(LocalSigner(secret))


def _recipient_key() -> OotleSecretKey:
    return OotleSecretKey.random(Network.LOCAL_NET)


def test_account_pay_fee_emits_fee_instruction(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        builder = client.account().pay_fee(500)
        unsigned = json.loads(builder._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    fee = unsigned["fee_instructions"]
    assert len(fee) == 1
    assert fee[0]["CallMethod"]["method"] == "pay_fee"


def test_account_public_transfer_emits_correct_instructions(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    recipient = _recipient_key().to_address()
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        builder = client.account().pay_fee(500).public_transfer(recipient, _SOME_RESOURCE, 1 * TARI)
        unsigned = json.loads(builder._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    instructions = unsigned["instructions"]
    assert instructions[0]["CallMethod"]["method"] == "withdraw"
    assert instructions[1] == {"PutLastInstructionOutputOnWorkspace": {"key": 0}}
    assert "CreateAccount" in instructions[2]
    assert instructions[2]["CreateAccount"]["owner_public_key"] == recipient.owner_pk.hex()


def test_account_publish_template_bytes(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        builder = client.account().publish_template(b"\xde\xad\xbe\xef")
        unsigned = json.loads(builder._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    instructions = unsigned["instructions"]
    assert instructions[0] == {"PublishTemplate": {"binary": 0, "metadata_hash": None}}
    assert unsigned["blobs"] == ["3q2+7w=="]


def test_account_publish_template_blob_wrapper(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        builder = client.account().publish_template(TemplateBlob(blob=b"\x01\x02"))
        unsigned = json.loads(builder._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    instructions = unsigned["instructions"]
    assert instructions[0] == {"PublishTemplate": {"binary": 0, "metadata_hash": None}}
    assert unsigned["blobs"] == ["AQI="]


def test_account_transfer_requires_positive_amount(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    recipient = _recipient_key().to_address()
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        with pytest.raises(InvalidArgumentError):
            client.account().public_transfer(recipient, _SOME_RESOURCE, 0)


def test_account_without_wallet_raises_at_default_signer(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx") as client:
        with pytest.raises(InvalidArgumentError):
            _ = client.account().default_signer_address


def test_account_fluent_returns_self(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    recipient = _recipient_key().to_address()
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.account()
        assert b.pay_fee(1) is b
        assert b.public_transfer(recipient, _SOME_RESOURCE, 1) is b
        assert b.publish_template(b"\x00") is b


def test_account_multi_transfer_unique_workspace_labels(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    r1 = _recipient_key().to_address()
    r2 = _recipient_key().to_address()
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        builder = (
            client.account()
            .public_transfer(r1, _SOME_RESOURCE, 1 * TARI)
            .public_transfer(r2, _SOME_RESOURCE, 2 * TARI)
        )
        unsigned = json.loads(builder._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    instructions = unsigned["instructions"]
    # 2 withdraws + 2 put-on-workspace + 2 create-account = 6 instructions
    assert len(instructions) == 6
    # workspace keys must be unique
    workspace_keys = [
        i["PutLastInstructionOutputOnWorkspace"]["key"]
        for i in instructions
        if "PutLastInstructionOutputOnWorkspace" in i
    ]
    assert len(set(workspace_keys)) == 2


def test_account_want_list_populated(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    recipient = _recipient_key().to_address()
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.account().pay_fee(500).public_transfer(recipient, _SOME_RESOURCE, 1)

    want_types = {type(w).__name__ for w in b._want_list}  # pyright: ignore[reportPrivateUsage]  # internal access
    assert "VaultForResource" in want_types
    assert "SpecificSubstate" in want_types
    _ = TARI_TOKEN  # used implicitly via pay_fee
