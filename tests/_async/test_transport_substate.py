"""Transport — single + batched substate fetches."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from ootle._async._transport import AsyncIndexerTransport
from ootle._types.substate import SubstateId, VaultSubstateValue


async def test_fetch_substate_happy_path(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/substates/vault_abc",
        json={
            "version": 7,
            "substate": {
                "Vault": {
                    "resource_container": {
                        "Stealth": {
                            "address": "resource_aaaa",
                            "revealed_amount": "100",
                            "locked_amount": "0",
                        }
                    },
                    "freeze_flags": 0,
                }
            },
        },
    )
    async with AsyncIndexerTransport("http://idx") as transport:
        result = await transport.fetch_substate(SubstateId("vault_abc"))
    assert result is not None
    assert result.id.opaque == "vault_abc"
    assert result.version == 7
    assert isinstance(result.value, VaultSubstateValue)
    assert result.value.container_kind == "stealth"
    assert int(result.value.balance) == 100


async def test_fetch_substate_404_returns_none(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="http://idx/substates/component_missing",
        status_code=404,
    )
    async with AsyncIndexerTransport("http://idx") as transport:
        result = await transport.fetch_substate(SubstateId("component_missing"))
    assert result is None


async def test_fetch_substates_chunks_at_20(httpx_mock: HTTPXMock) -> None:
    # 25 ids → 2 calls (20 + 5).
    ids = [SubstateId(f"vault_{i:02x}") for i in range(25)]

    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {}},
    )
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {}},
    )

    async with AsyncIndexerTransport("http://idx") as transport:
        out = await transport.fetch_substates(ids)
    assert out == {}
    posted = [r for r in httpx_mock.get_requests() if r.url.path == "/substates/fetch"]
    assert len(posted) == 2
