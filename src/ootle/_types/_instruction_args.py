"""Workspace / component references, ``InstructionArg`` variants, and literal helpers.

Split out of :mod:`ootle._types.instructions` to keep individual files under the
project's 200-line ceiling. Imported and re-exported by ``instructions.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ootle._types._cbor import (
    cbor_encode_amount,
    cbor_encode_metadata,
    cbor_encode_resource_address,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ootle._types.address import ComponentAddress, ResourceAddress
    from ootle._types.amount import Amount


# --- Workspace + component-reference shapes -----------------------------------


@dataclass(frozen=True, slots=True)
class WorkspaceOffsetId:
    """``{ id: WorkspaceId, offset: number | null }`` — workspace reference."""

    id: int
    offset: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "offset": self.offset}


@dataclass(frozen=True, slots=True)
class ComponentRefAddress:
    """``ComponentReference::Address(ComponentAddress)``."""

    address: ComponentAddress

    def to_json(self) -> dict[str, Any]:
        return {"Address": str(self.address)}


@dataclass(frozen=True, slots=True)
class ComponentRefWorkspace:
    """``ComponentReference::Workspace(WorkspaceId)`` — bare ``u16`` workspace id.

    Note that the Rust enum carries a ``WorkspaceId`` (u16), not a
    ``WorkspaceOffsetId`` struct — the latter only appears inside
    :class:`InstructionArg::Workspace`.
    """

    workspace_id: int

    def to_json(self) -> dict[str, Any]:
        return {"Workspace": self.workspace_id}


ComponentReference = ComponentRefAddress | ComponentRefWorkspace


# --- Instruction args ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InstructionArgLiteral:
    """``InstructionArg::Literal(Bytes)`` — hex-encoded CBOR body."""

    body_hex: str

    def to_json(self) -> dict[str, Any]:
        return {"Literal": self.body_hex}


@dataclass(frozen=True, slots=True)
class InstructionArgWorkspace:
    """``InstructionArg::Workspace(WorkspaceOffsetId)``."""

    workspace: WorkspaceOffsetId

    def to_json(self) -> dict[str, Any]:
        return {"Workspace": self.workspace.to_json()}


InstructionArg = InstructionArgLiteral | InstructionArgWorkspace


def amount_literal(value: Amount | int) -> InstructionArgLiteral:
    """Build an ``InstructionArg::Literal`` carrying a CBOR-encoded Amount."""
    return InstructionArgLiteral(body_hex=cbor_encode_amount(value).hex())


def resource_address_literal(addr: ResourceAddress) -> InstructionArgLiteral:
    """Build an ``InstructionArg::Literal`` carrying a CBOR-encoded ResourceAddress."""
    return InstructionArgLiteral(body_hex=cbor_encode_resource_address(addr).hex())


def metadata_literal(entries: Mapping[str, str]) -> InstructionArgLiteral:
    """Build an ``InstructionArg::Literal`` carrying a CBOR-encoded Metadata map."""
    return InstructionArgLiteral(body_hex=cbor_encode_metadata(entries).hex())
