"""Shared helpers for ``StealthTransfer`` sync test suites.

Hand-written counterpart of ``tests/_async/stealth/_builder_helpers.py``;
the stealth test corpus is hand-maintained on the sync side (see
``scripts/unasync.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle import LocalSigner, OotleClient, OotleSecretKey, OotleWallet
from ootle._crypto._wasm_provider import WasmCryptoProvider
from ootle._types.address import ComponentAddress, ResourceAddress
from ootle._types.network import Network
from tests._sync._helpers import network_response

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock

    from ootle._types.address import Address


RESOURCE: ResourceAddress = ResourceAddress(
    "resource_0101010101010101010101010101010101010101010101010101010101010101"
)
COMPONENT: ComponentAddress = ComponentAddress(
    "component_0202020202020202020202020202020202020202020202020202020202020202"
)
COMMITMENT: bytes = b"\xaa" * 32
UTXO_ID: str = f"utxo_{str(RESOURCE).removeprefix('resource_')}_{COMMITMENT.hex()}"


def make_wallet() -> OotleWallet:
    """Build a wallet with a single random signer on LocalNet."""
    return OotleWallet(LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)))


def recipient_address() -> Address:
    """Generate a fresh recipient :class:`Address`."""
    return OotleSecretKey.random(Network.LOCAL_NET).to_address()


VAULT_ID: str = "vault_" + ("cc" * 32)
SIGNER_VAULT_ID: str = "vault_" + ("dd" * 32)


def stub_substates_for_account(httpx_mock: HTTPXMock, signer_account: str) -> None:
    """Mock indexer ``substates/fetch`` for the synthetic ``COMPONENT`` and the signer."""
    from ootle._types._tari_constants import TARI_TOKEN  # noqa: PLC0415
    from tests._helpers.substates import (  # noqa: PLC0415
        component_value,
        envelope,
        fungible_vault_value,
    )

    httpx_mock.add_response(
        url="http://idx/substates/fetch",
        method="POST",
        json={
            "substates": {
                str(COMPONENT): envelope(component_value({str(RESOURCE): VAULT_ID})),
                VAULT_ID: envelope(fungible_vault_value(str(RESOURCE), 1_000)),
                str(RESOURCE): envelope({"Resource": {"total_supply": "1000"}}),
                UTXO_ID: envelope(
                    {
                        "Utxo": {
                            "output": {
                                "output": {
                                    "public_nonce": "ff" * 32,
                                    "encrypted_data": "00" * 80,
                                    "minimum_value_promise": 0,
                                    "viewable_balance": None,
                                },
                                "spend_condition": {"Signed": "ff" * 32},
                                "tag": 1,
                            },
                            "is_frozen": False,
                        }
                    }
                ),
                signer_account: envelope(
                    component_value({str(TARI_TOKEN): SIGNER_VAULT_ID, str(RESOURCE): VAULT_ID})
                ),
                SIGNER_VAULT_ID: envelope(fungible_vault_value(str(TARI_TOKEN), 10_000)),
            }
        },
        is_reusable=True,
        is_optional=True,
    )


def make_client(
    httpx_mock: HTTPXMock,
    *,
    crypto: object | None = None,
) -> OotleClient:
    """Connect an opened :class:`OotleClient` against a mocked indexer.

    Defaults ``crypto`` to the real :class:`WasmCryptoProvider` so the
    builder/authorizer/read-helper paths run against the vendored blob
    end-to-end (no network). Pass an explicit ``crypto=`` (e.g. a
    non-stealth object) to exercise the provider-validation guard.
    """
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    wallet = make_wallet()
    signer_account = str(wallet.default_address.to_component_address())
    stub_substates_for_account(httpx_mock, signer_account)
    provider = crypto if crypto is not None else WasmCryptoProvider.load_default()
    client = OotleClient.connect(
        "http://idx",
        wallet=wallet,
        # accepts an arbitrary object so guard tests can pass a non-stealth crypto
        crypto=provider,  # pyright: ignore[reportArgumentType]  # intentional type mismatch under test
    )
    return client.open()
