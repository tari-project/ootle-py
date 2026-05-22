"""``AsyncTransactionInputResolver`` tests."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle._async._resolver import AsyncTransactionInputResolver
from ootle._async._transport import AsyncIndexerTransport
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ComponentAddress, ResourceAddress
from ootle._types.substate import SubstateId
from ootle._types.transaction import UnsignedTransaction
from ootle._types.want_input import WantInput
from ootle.errors import IndexerClientError
from tests._helpers.substates import component_value, envelope, fungible_vault_value


def _empty_unsigned() -> UnsignedTransaction:
    return UnsignedTransaction(
        json=json.dumps(
            {
                "network": 0x10,
                "fee_instructions": [],
                "instructions": [],
                "inputs": [],
                "min_epoch": None,
                "max_epoch": None,
                "is_seal_signer_authorized": True,
                "dry_run": False,
            }
        )
    )


async def test_empty_want_list_returns_unchanged() -> None:
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    unsigned = _empty_unsigned()
    out = await resolver.resolve(unsigned, set())
    await transport.aclose()
    assert out is unsigned


async def test_required_specific_substate_present_added(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {"component_z": {"version": 1, "substate": {"Component": {}}}}},
    )
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    want = WantInput.SpecificSubstate(id=SubstateId("component_z"), required=True)
    out = await resolver.resolve(_empty_unsigned(), {want})
    await transport.aclose()
    body = json.loads(out.json)
    assert body["inputs"] == [{"substate_id": "component_z", "version": None}]


async def test_required_specific_substate_missing_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/substates/fetch", method="POST", json={"substates": {}})
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    want = WantInput.SpecificSubstate(id=SubstateId("component_missing"), required=True)
    with pytest.raises(IndexerClientError, match="required substate"):
        await resolver.resolve(_empty_unsigned(), {want})
    await transport.aclose()


async def test_optional_specific_substate_present_added(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {"component_z": {"version": 1, "substate": {"Component": {}}}}},
    )
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    want = WantInput.SpecificSubstate(id=SubstateId("component_z"), required=False)
    out = await resolver.resolve(_empty_unsigned(), {want})
    await transport.aclose()
    body = json.loads(out.json)
    assert body["inputs"] == [{"substate_id": "component_z", "version": None}]


async def test_optional_specific_substate_missing_skipped(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/substates/fetch", method="POST", json={"substates": {}})
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    want = WantInput.SpecificSubstate(id=SubstateId("component_missing"), required=False)
    out = await resolver.resolve(_empty_unsigned(), {want})
    await transport.aclose()
    assert json.loads(out.json)["inputs"] == []


async def test_vault_for_resource_two_pass_fixed_point(httpx_mock: HTTPXMock) -> None:
    component = "component_acc"
    vault = "vault_" + ("aa" * 32)
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {component: envelope(component_value({TARI_TOKEN: vault}), version=1)}},
    )
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {vault: envelope(fungible_vault_value(TARI_TOKEN, 100), version=1)}},
    )
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    want = WantInput.VaultForResource(
        component=ComponentAddress(component),
        resource=ResourceAddress(TARI_TOKEN),
        required=True,
    )
    out = await resolver.resolve(_empty_unsigned(), {want})
    await transport.aclose()
    body = json.loads(out.json)
    ids = {req["substate_id"] for req in body["inputs"]}
    assert vault in ids
    # TARI_TOKEN is implicit, so the resource itself isn't added
    assert TARI_TOKEN not in ids
    assert len(httpx_mock.get_requests()) == 2


async def test_required_vault_missing_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/substates/fetch", method="POST", json={"substates": {}})
    transport = AsyncIndexerTransport("http://idx")
    resolver = AsyncTransactionInputResolver(transport)
    want = WantInput.VaultForResource(
        component=ComponentAddress("component_missing"),
        resource=ResourceAddress(TARI_TOKEN),
        required=True,
    )
    with pytest.raises(IndexerClientError):
        await resolver.resolve(_empty_unsigned(), {want})
    await transport.aclose()
