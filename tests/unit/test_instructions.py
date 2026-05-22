"""``args()``, ``workspace()``, and the ``Arg`` discriminated union."""

from __future__ import annotations

import pytest

from ootle._instructions import Arg, args, metadata, workspace
from ootle._types.address import ComponentAddress
from ootle._types.amount import Amount
from ootle.errors import InvalidArgumentError


def test_int_lifts_to_literal() -> None:
    [a] = args(42)
    assert isinstance(a, Arg.Literal)
    assert a.value == 42


def test_amount_lifts_to_literal_preserving_type() -> None:
    [a] = args(Amount(7))
    assert isinstance(a, Arg.Literal)
    assert isinstance(a.value, Amount)
    assert a.value == 7


def test_bool_lifts_to_literal() -> None:
    [a] = args(True)
    assert isinstance(a, Arg.Literal)
    assert a.value is True


def test_str_lifts_to_literal() -> None:
    [a] = args("hello")
    assert isinstance(a, Arg.Literal)
    assert a.value == "hello"


def test_bytes_lifts_to_literal() -> None:
    [a] = args(b"\x01\x02")
    assert isinstance(a, Arg.Literal)
    assert a.value == b"\x01\x02"


def test_existing_arg_passes_through() -> None:
    payload = Arg.Address(addr=ComponentAddress("c-1"))
    [a] = args(payload)
    assert a is payload


def test_mixed_args_lift_in_order() -> None:
    out = args(42, "hello", b"x", Amount(100))
    assert all(isinstance(o, Arg.Literal) for o in out)
    assert [o.value for o in out if isinstance(o, Arg.Literal)] == [
        42,
        "hello",
        b"x",
        Amount(100),
    ]


def test_workspace_returns_named_arg() -> None:
    arg = workspace("bucket")
    assert isinstance(arg, Arg.NamedArg)
    assert arg.label == "bucket"
    assert arg == Arg.NamedArg(label="bucket")


def test_metadata_from_kwargs_returns_metadata_arg() -> None:
    arg = metadata(provider_name="Acme")
    assert isinstance(arg, Arg.Metadata)
    assert dict(arg.entries) == {"provider_name": "Acme"}


def test_metadata_from_mapping_returns_metadata_arg() -> None:
    arg = metadata({"a": "1", "b": "2"})
    assert isinstance(arg, Arg.Metadata)
    assert dict(arg.entries) == {"a": "1", "b": "2"}


def test_metadata_merges_mapping_and_kwargs() -> None:
    arg = metadata({"a": "1"}, b="2")
    assert isinstance(arg, Arg.Metadata)
    assert dict(arg.entries) == {"a": "1", "b": "2"}


def test_metadata_passthrough_in_args() -> None:
    md = metadata(x="y")
    [a] = args(md)
    assert a is md


def test_invalid_value_raises_invalid_argument_error() -> None:
    with pytest.raises(InvalidArgumentError):
        args(object())


def test_dict_value_rejected() -> None:
    with pytest.raises(InvalidArgumentError):
        args({"a": 1})


def test_list_value_rejected() -> None:
    with pytest.raises(InvalidArgumentError):
        args([1, 2, 3])


def test_arg_members_hash_and_compare() -> None:
    a = Arg.Literal(value=1)
    b = Arg.Literal(value=1)
    c = Arg.NamedArg(label="x")
    d = Arg.Address(addr=ComponentAddress("c"))
    assert a == b
    assert hash(a) == hash(b)
    assert {a, b, c, d} == {a, c, d}
