"""``Instruction`` enum variants.

Split out of :mod:`ootle._types.instructions` to keep individual files under
the project's 200-line ceiling. Imported and re-exported by ``instructions.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ootle._types._instruction_args import (
        ComponentReference,
        InstructionArg,
        WorkspaceOffsetId,
    )
    from ootle._types.address import ResourceAddress, TemplateAddress
    from ootle._types.stealth import StealthTransferStatement


@dataclass(frozen=True, slots=True)
class CallMethod:
    call: ComponentReference
    method: str
    args: tuple[InstructionArg, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "CallMethod": {
                "call": self.call.to_json(),
                "method": self.method,
                "args": [a.to_json() for a in self.args],
            }
        }


@dataclass(frozen=True, slots=True)
class PutLastInstructionOutputOnWorkspace:
    key: int

    def to_json(self) -> dict[str, Any]:
        return {"PutLastInstructionOutputOnWorkspace": {"key": self.key}}


@dataclass(frozen=True, slots=True)
class CreateAccount:
    owner_public_key: bytes
    bucket_workspace_id: WorkspaceOffsetId | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "CreateAccount": {
                "owner_public_key": self.owner_public_key.hex(),
                "owner_rule": None,
                "access_rules": None,
                "bucket_workspace_id": (
                    self.bucket_workspace_id.to_json()
                    if self.bucket_workspace_id is not None
                    else None
                ),
            }
        }


@dataclass(frozen=True, slots=True)
class PayFeeFromBucket:
    bucket: WorkspaceOffsetId

    def to_json(self) -> dict[str, Any]:
        return {"PayFeeFromBucket": {"bucket": self.bucket.to_json()}}


@dataclass(frozen=True, slots=True)
class CallFunction:
    """``Instruction::CallFunction`` — call a template function by name."""

    template_address: TemplateAddress
    function: str
    args: tuple[InstructionArg, ...] = ()

    def to_json(self) -> dict[str, Any]:
        # The instruction wire type is `Hash32` (bare 64-char hex), unlike the
        # `template_<hex>` form `SubstateId::Template` displays — accept either.
        return {
            "CallFunction": {
                "address": str(self.template_address).removeprefix("template_"),
                "function": self.function,
                "args": [a.to_json() for a in self.args],
            }
        }


@dataclass(frozen=True, slots=True)
class PublishTemplate:
    """``Instruction::PublishTemplate`` — ``binary`` is a ``BlobIndex`` (u8) into the
    surrounding transaction's ``blobs`` list."""

    binary: int
    metadata_hash: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {"PublishTemplate": {"binary": self.binary, "metadata_hash": self.metadata_hash}}


@dataclass(frozen=True, slots=True)
class StealthTransferInstruction:
    """``Instruction::StealthTransfer`` — confidential transfer wire instruction.

    Mirrors Rust's ``Instruction::StealthTransfer { resource_address_ref,
    statement, revealed_input_bucket }``. ``resource`` is the resource
    being transferred (always concrete in v1; the Workspace ref form is
    not yet exposed). ``revealed_input_bucket`` points to the workspace
    bucket carrying any revealed-amount input contribution, or ``None``
    when the transfer is fully stealth.
    """

    resource: ResourceAddress
    statement: StealthTransferStatement
    revealed_input_bucket: WorkspaceOffsetId | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "StealthTransfer": {
                "resource_address_ref": {"Address": str(self.resource)},
                "statement": self.statement.to_json(),
                "revealed_input_bucket": (
                    None
                    if self.revealed_input_bucket is None
                    else self.revealed_input_bucket.to_json()
                ),
            }
        }
