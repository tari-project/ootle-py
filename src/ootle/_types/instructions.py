"""Instruction / InstructionArg JSON shapes.

These dataclasses mirror the Rust ``tari_ootle_transaction`` types
one-for-one and serialize to the JSON shape that the WASM
``sealTransaction`` and ``borEncodeTransaction`` entry points accept.

``InstructionArg.Literal`` is a hex-encoded string of CBOR bytes; see
:mod:`ootle._types._cbor` for the encoding helpers and
:mod:`ootle._types._tari_constants` for well-known on-chain addresses.

The concrete variants live in sibling modules to keep individual files under
the project's 200-line ceiling; this module re-exports them so external
consumers can keep importing from ``ootle._types.instructions``.
"""

from __future__ import annotations

from ootle._types._instruction_args import (
    ComponentRefAddress,
    ComponentReference,
    ComponentRefWorkspace,
    InstructionArg,
    InstructionArgLiteral,
    InstructionArgWorkspace,
    WorkspaceOffsetId,
    amount_literal,
    metadata_literal,
    resource_address_literal,
)
from ootle._types._instruction_variants import (
    CallFunction,
    CallMethod,
    CreateAccount,
    PayFeeFromBucket,
    PublishTemplate,
    PutLastInstructionOutputOnWorkspace,
    StealthTransferInstruction,
)

Instruction = (
    CallMethod
    | CallFunction
    | PutLastInstructionOutputOnWorkspace
    | CreateAccount
    | PayFeeFromBucket
    | PublishTemplate
    | StealthTransferInstruction
)

__all__ = [
    "CallFunction",
    "CallMethod",
    "ComponentRefAddress",
    "ComponentRefWorkspace",
    "ComponentReference",
    "CreateAccount",
    "Instruction",
    "InstructionArg",
    "InstructionArgLiteral",
    "InstructionArgWorkspace",
    "PayFeeFromBucket",
    "PublishTemplate",
    "PutLastInstructionOutputOnWorkspace",
    "StealthTransferInstruction",
    "WorkspaceOffsetId",
    "amount_literal",
    "metadata_literal",
    "resource_address_literal",
]
