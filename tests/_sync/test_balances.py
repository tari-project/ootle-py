"""Account balance helpers — algorithm + walking the component state."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from ootle._sync.client import OotleClient
from ootle._types.address import ComponentAddress, ResourceAddress
from ootle._types.amount import Amount
from tests._helpers.substates import component_value, envelope, fungible_vault_value

from ._helpers import network_response

VAULT_TARI = "vault_" + ("aa" * 32)
VAULT_USDT = "vault_" + ("bb" * 32)
RESOURCE_TARI = "resource_" + ("11" * 32)
RESOURCE_USDT = "resource_" + ("22" * 32)
ACCOUNT = ComponentAddress("component_account_one")


def test_get_account_balance_returns_matching_resource(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    httpx_mock.add_response(
        url=f"http://idx/substates/{ACCOUNT}",
        json=envelope(component_value({RESOURCE_TARI: VAULT_TARI, RESOURCE_USDT: VAULT_USDT})),
    )
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={
            "substates": {
                VAULT_TARI: envelope(fungible_vault_value(RESOURCE_TARI, 100)),
                VAULT_USDT: envelope(fungible_vault_value(RESOURCE_USDT, 25)),
            }
        },
    )

    with OotleClient.connect("http://idx") as client:
        bal = client.get_account_balance(ACCOUNT, ResourceAddress(RESOURCE_TARI))
    assert bal == Amount(100)


def test_get_account_balance_missing_resource_returns_zero(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    httpx_mock.add_response(
        url=f"http://idx/substates/{ACCOUNT}",
        json=envelope(component_value({RESOURCE_TARI: VAULT_TARI})),
    )
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={"substates": {VAULT_TARI: envelope(fungible_vault_value(RESOURCE_TARI, 100))}},
    )

    with OotleClient.connect("http://idx") as client:
        bal = client.get_account_balance(ACCOUNT, ResourceAddress("resource_other"))
    assert bal == Amount(0)


def test_get_account_balances_returns_all_vaults(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    httpx_mock.add_response(
        url=f"http://idx/substates/{ACCOUNT}",
        json=envelope(component_value({RESOURCE_TARI: VAULT_TARI, RESOURCE_USDT: VAULT_USDT})),
    )
    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={
            "substates": {
                VAULT_TARI: envelope(fungible_vault_value(RESOURCE_TARI, 100)),
                VAULT_USDT: envelope(fungible_vault_value(RESOURCE_USDT, 25)),
            }
        },
    )

    with OotleClient.connect("http://idx") as client:
        balances = client.get_account_balances(ACCOUNT)
    assert balances == {
        ResourceAddress(RESOURCE_TARI): Amount(100),
        ResourceAddress(RESOURCE_USDT): Amount(25),
    }


def test_get_account_balances_missing_account_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    httpx_mock.add_response(url=f"http://idx/substates/{ACCOUNT}", status_code=404)

    with OotleClient.connect("http://idx") as client:
        balances = client.get_account_balances(ACCOUNT)
    assert balances == {}
