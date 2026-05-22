"""Extra coverage for ``IComponent`` argument lifters and want-list registration."""

from __future__ import annotations

import json

import cbor2
from pytest_httpx import HTTPXMock

from ootle import (
    Arg,
    OotleClient,
    LocalSigner,
    OotleSecretKey,
    OotleWallet,
    metadata,
    workspace,
)
from ootle._types.address import ComponentAddress, ResourceAddress
from ootle._types.network import Network
from ootle._types.substate import SubstateId
from ootle._types.want_input import WantInput

from ._helpers import network_response

_COMP = ComponentAddress("component_abc")
_RES = ResourceAddress("resource_xyz")


def _wallet() -> OotleWallet:
    return OotleWallet(LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)))


def test_call_method_with_bool_arg(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(_COMP, "set", args=[Arg.Literal(True)])
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    arg = body["instructions"][0]["CallMethod"]["args"][0]
    assert cbor2.loads(bytes.fromhex(arg["Literal"])) is True


def test_call_method_with_str_arg(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(_COMP, "name", args=[Arg.Literal("alice")])
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    arg = body["instructions"][0]["CallMethod"]["args"][0]
    assert cbor2.loads(bytes.fromhex(arg["Literal"])) == "alice"


def test_call_method_with_bytes_arg(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(_COMP, "blob", args=[Arg.Literal(b"\x00\xff")])
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    arg = body["instructions"][0]["CallMethod"]["args"][0]
    assert cbor2.loads(bytes.fromhex(arg["Literal"])) == b"\x00\xff"


def test_call_method_with_named_workspace_arg(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = (
            client.component()
            .call_method(_COMP, "take")
            .put_last_instruction_output_on_workspace("bucket")
            .call_method(_COMP, "deposit", args=[workspace("bucket")])
        )
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    last = body["instructions"][2]["CallMethod"]
    arg = last["args"][0]
    assert arg["Workspace"]["id"] == 0


def test_call_method_with_address_arg(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(
            _COMP, "with_resource", args=[Arg.Address(ResourceAddress("resource_aa"))]
        )
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    arg = body["instructions"][0]["CallMethod"]["args"][0]
    assert "Literal" in arg


def test_call_method_with_metadata_arg(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(
            _COMP, "configure", args=[metadata(provider_name="Acme")]
        )
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    arg = body["instructions"][0]["CallMethod"]["args"][0]
    decoded = cbor2.loads(bytes.fromhex(arg["Literal"]))
    assert isinstance(decoded, cbor2.CBORTag)
    assert decoded.tag == 129
    assert decoded.value == {"provider_name": "Acme"}


def test_want_substate_registers_specific_substate(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().want_substate(SubstateId("component_x"), required=True)
    wants = b._want_list  # pyright: ignore[reportPrivateUsage]  # internal access
    assert any(
        isinstance(w, WantInput.SpecificSubstate) and w.id.opaque == "component_x" and w.required
        for w in wants
    )


def test_want_vault_for_registers_vault(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().want_vault_for(_COMP, _RES, required=False)
    wants = b._want_list  # pyright: ignore[reportPrivateUsage]  # internal access
    assert any(isinstance(w, WantInput.VaultForResource) and not w.required for w in wants)
