"""``Arg`` discriminated union plus the ``args()`` and ``workspace()`` lifters.

These helpers are pure data transformations consumed by the M4-M6
builders. ``args(...)`` lifts loose Python values into typed ``Arg``
instances per the table in ``08-templates.md``; ``workspace(label)`` is
the sugar for a workspace reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from ootle._types.amount import Amount
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ootle._types.address import (
        ComponentAddress,
        ResourceAddress,
        TemplateAddress,
    )

LiteralValue = int | str | bytes | bool | Amount


class Arg:
    """Namespace for the three argument variants.

    The members are nested frozen-slots dataclasses; deconstruct via
    ``match`` on instances of :class:`Arg.Literal`, :class:`Arg.NamedArg`,
    or :class:`Arg.Address`.
    """

    @dataclass(frozen=True, slots=True)
    class Literal:
        """A literal argument value (number, string, bytes, bool, Amount)."""

        value: LiteralValue

    @dataclass(frozen=True, slots=True)
    class NamedArg:
        """A reference to a previously named workspace bucket."""

        label: str

    @dataclass(frozen=True, slots=True)
    class Address:
        """A reference to a component / resource / template address."""

        addr: ComponentAddress | ResourceAddress | TemplateAddress

    @dataclass(frozen=True, slots=True)
    class Metadata:
        """A ``BTreeMap<String, String>`` metadata literal (CBOR tag 129).

        Templates that take a ``Metadata`` parameter (e.g. resource builders,
        ``stable_coin::instantiate``) expect this tagged-map encoding.
        """

        entries: Mapping[str, str]


ArgVariant = Arg.Literal | Arg.NamedArg | Arg.Address | Arg.Metadata


def args(*items: Any) -> list[ArgVariant]:
    """Lift a mix of loose Python values into a list of :class:`Arg`.

    Lifting rules (per ``08-templates.md``):

    ============================ ========================
    Python type                  Lifted to
    ============================ ========================
    ``int`` (incl. :class:`Amount`) ``Arg.Literal``
    ``str``                      ``Arg.Literal``
    ``bytes``                    ``Arg.Literal``
    ``bool``                     ``Arg.Literal``
    ``ComponentAddress`` etc.    ``Arg.Address``
    ``Arg.*`` instance           passthrough
    everything else              ``InvalidArgumentError``
    ============================ ========================

    Note: address types are :class:`typing.NewType` aliases over ``str``
    and therefore indistinguishable at runtime. The lifter treats every
    ``str`` as ``Arg.Literal``; callers wanting an ``Arg.Address`` use
    ``Arg.Address(addr)`` directly.
    """
    return [_lift_one(item) for item in items]


def workspace(label: str) -> ArgVariant:
    """Sugar for :class:`Arg.NamedArg` references."""
    return Arg.NamedArg(label=label)


def metadata(entries: Mapping[str, str] | None = None, /, **kwargs: str) -> ArgVariant:
    """Build an :class:`Arg.Metadata` literal from a mapping or kwargs.

    Pass keys either positionally as a mapping or as keyword arguments::

        metadata(provider_name="Acme", website="acme.example")
        metadata({"provider_name": "Acme"})
    """
    merged: dict[str, str] = {}
    if entries is not None:
        merged.update(entries)
    merged.update(kwargs)
    return Arg.Metadata(entries=MappingProxyType(merged))


def _lift_one(value: Any) -> ArgVariant:
    if isinstance(value, Arg.Literal | Arg.NamedArg | Arg.Address | Arg.Metadata):
        return value
    if isinstance(value, bool):
        return Arg.Literal(value=value)
    if isinstance(value, Amount):
        return Arg.Literal(value=value)
    if isinstance(value, int):
        return Arg.Literal(value=value)
    if isinstance(value, str):
        return Arg.Literal(value=value)
    if isinstance(value, bytes):
        return Arg.Literal(value=value)
    msg = f"args() cannot lift value of type {type(value).__name__!r}: {value!r}"
    raise InvalidArgumentError(msg)
