"""``IFaucet`` tests — fluent shape + emitted JSON envelope."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle import OotleClient, LocalSigner, OotleSecretKey, OotleWallet
from ootle._types._tari_constants import (
    XTR_FAUCET_CLAIM_RESOURCE_ADDRESS,
    XTR_FAUCET_COMPONENT_ADDRESS,
    XTR_FAUCET_VAULT_ADDRESS,
)
from ootle._types.network import Network
from ootle.errors import InvalidArgumentError

from ._helpers import network_response


def _wallet() -> OotleWallet:
    secret = OotleSecretKey.random(Network.LOCAL_NET)
    return OotleWallet(LocalSigner(secret))


def test_faucet_take_funds_emits_full_instruction_block(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        builder = client.faucet().take_funds().pay_fee(500)
        unsigned = json.loads(builder._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    fee = unsigned["fee_instructions"]
    # Sequence: CreateAccount → PutOnWorkspace → faucet.take(workspace) → pay_fee
    create = fee[0]["CreateAccount"]
    assert create["owner_public_key"] is not None
    take = fee[2]["CallMethod"]
    assert take["call"] == {"Address": XTR_FAUCET_COMPONENT_ADDRESS}
    assert take["method"] == "take"
    assert take["args"][0] == {"Workspace": {"id": 0, "offset": None}}
    pay = fee[-1]["CallMethod"]
    assert pay["method"] == "pay_fee"
    substate_ids = {req["substate_id"] for req in unsigned["inputs"]}
    assert XTR_FAUCET_COMPONENT_ADDRESS in substate_ids
    assert XTR_FAUCET_VAULT_ADDRESS in substate_ids
    assert XTR_FAUCET_CLAIM_RESOURCE_ADDRESS in substate_ids


def test_faucet_without_wallet_raises_at_default_signer(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx") as client:
        with pytest.raises(InvalidArgumentError):
            _ = client.faucet().default_signer_address


def test_faucet_fluent_returns_self(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.faucet()
        assert b.take_funds() is b
        assert b.pay_fee(1) is b
