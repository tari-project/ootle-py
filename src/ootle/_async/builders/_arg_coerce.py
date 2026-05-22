"""Argument coercion helpers for :class:`IAsyncComponent`.

Pure, builder-state-free converters that turn user-facing
:class:`~ootle._instructions.Arg` values and raw Python literals into wire
:class:`~ootle._types.instructions.InstructionArg` values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ootle._types.instructions import (
    InstructionArgLiteral,
    InstructionArgWorkspace,
    WorkspaceOffsetId,
    amount_literal,
    metadata_literal,
    resource_address_literal,
)
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._instructions import ArgVariant
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.instructions import InstructionArg


def cbor_literal(value: Any) -> InstructionArgLiteral:
    """CBOR-encode a literal Python value into an ``InstructionArgLiteral``."""
    from ootle._types._cbor import (  # noqa: PLC0415
        cbor_encode_bool,
        cbor_encode_bytes,
        cbor_encode_str,
    )

    match value:
        case bool():
            return InstructionArgLiteral(body_hex=cbor_encode_bool(value).hex())
        case int():
            return amount_literal(value)
        case str():
            return InstructionArgLiteral(body_hex=cbor_encode_str(value).hex())
        case bytes():
            return InstructionArgLiteral(body_hex=cbor_encode_bytes(value).hex())
        case _:
            msg = f"cannot CBOR-encode value of type {type(value).__name__!r} as an InstructionArg"
            raise InvalidArgumentError(msg)


def convert_arg(builder: TransactionBuilder, arg: ArgVariant) -> InstructionArg:
    """Convert a user-facing :class:`~ootle._instructions.Arg` to a wire ``InstructionArg``.

    Args:
        builder: The owning transaction builder, used to resolve workspace labels.
        arg: The user-facing argument to convert.
    """
    from ootle._instructions import Arg  # noqa: PLC0415

    match arg:
        case Arg.NamedArg(label=label):
            wid: int = builder._resolve_workspace(label)  # pyright: ignore[reportPrivateUsage]  # internal access
            return InstructionArgWorkspace(WorkspaceOffsetId(id=wid))
        case Arg.Address(addr=addr):
            return resource_address_literal(addr)  # pyright: ignore[reportArgumentType]  # addr union narrowed by match
        case Arg.Metadata(entries=entries):
            return metadata_literal(entries)
        case Arg.Literal(value=v):
            return cbor_literal(v)
        case _:
            return cbor_literal(arg)  # pyright: ignore[reportArgumentType]  # fallthrough on never-typed arg
