"""``IComponent`` tests — instruction shapes, workspace plumbing, chain/then."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from ootle import OotleClient, LocalSigner, OotleSecretKey, OotleWallet
from ootle._instructions import Arg, workspace
from ootle._types.address import ComponentAddress, ResourceAddress, TemplateAddress
from ootle._types.network import Network
from ootle.errors import InvalidArgumentError

from ._helpers import network_response

_COMP = ComponentAddress("component_abc")
_RES = ResourceAddress("resource_xyz")
_TMPL = TemplateAddress("template_abc")


def _wallet() -> OotleWallet:
    return OotleWallet(LocalSigner(OotleSecretKey.random(Network.LOCAL_NET)))


def test_call_method_emits_correct_shape(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(_COMP, "my_method")
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    instr = body["instructions"][0]["CallMethod"]
    assert instr["call"] == {"Address": str(_COMP)}
    assert instr["method"] == "my_method"
    assert instr["args"] == []


def test_call_function_emits_correct_shape(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_function(_TMPL, "my_fn")
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    instr = body["instructions"][0]["CallFunction"]
    # The wire form is bare hex, even though callers may pass the `template_<hex>` form.
    assert instr["address"] == "abc"
    assert instr["function"] == "my_fn"
    assert instr["args"] == []


def test_call_function_accepts_bare_hex_template_address(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_function(TemplateAddress("abc"), "my_fn")
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    assert body["instructions"][0]["CallFunction"]["address"] == "abc"


def test_pay_fee_lands_in_fee_block(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().pay_fee(500)
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    assert body["instructions"] == []
    assert body["fee_instructions"][0]["CallMethod"]["method"] == "pay_fee"


def test_call_method_with_literal_arg_encodes_cbor(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().call_method(_COMP, "set_value", args=[Arg.Literal(42)])
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    args = body["instructions"][0]["CallMethod"]["args"]
    assert len(args) == 1 and "Literal" in args[0]


def test_put_last_instruction_output_on_workspace(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = (
            client.component()
            .call_method(_COMP, "take")
            .put_last_instruction_output_on_workspace("bucket")
        )
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    assert body["instructions"][1] == {"PutLastInstructionOutputOnWorkspace": {"key": 0}}


def test_call_method_on_workspace_emits_workspace_call(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = (
            client.component()
            .call_method(_COMP, "take")
            .put_last_instruction_output_on_workspace("bucket")
            .call_method(workspace("bucket"), "deposit")
        )
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    last = body["instructions"][2]["CallMethod"]
    assert last["call"] == {"Workspace": 0}
    assert last["method"] == "deposit"


def test_then_applies_callback(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component().then(lambda tb: tb.call_method("comp_x", "do_it"))
        body = json.loads(b._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    assert body["instructions"][0]["CallMethod"]["call"] == {"Address": "comp_x"}


def test_chain_merges_another_builder(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        a = client.component().call_method(_COMP, "step_a")
        b = client.component().call_method(_COMP, "step_b")
        a.chain(b)
        body = json.loads(a._builder.build_unsigned().json)  # pyright: ignore[reportPrivateUsage]  # internal access
    methods = [i["CallMethod"]["method"] for i in body["instructions"]]
    assert methods == ["step_a", "step_b"]


def test_fluent_methods_return_self(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        b = client.component()
        assert b.call_method(_COMP, "m") is b
        assert b.call_function(_TMPL, "f") is b
        assert b.want_vault_for(_COMP, _RES) is b
        assert b.want_all_vaults(_COMP) is b


def test_invalid_arg_raises(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://idx/network", json=network_response())
    with OotleClient.connect("http://idx", wallet=_wallet()) as client:
        with pytest.raises(InvalidArgumentError):
            client.component().call_method(_COMP, "m", args=[Arg.Literal(object())])  # pyright: ignore[reportArgumentType]  # intentional type mismatch under test
