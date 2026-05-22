"""Implementation of :meth:`TransactionBuilder.merge`.

Lives in its own module so ``_transaction_builder.py`` stays under the
200-line cap. Workspace ids and blob indices are offset to keep merged
builders collision-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle._types.instructions import (
    CallFunction,
    CallMethod,
    ComponentRefWorkspace,
    Instruction,
    InstructionArg,
    InstructionArgWorkspace,
    PublishTemplate,
    PutLastInstructionOutputOnWorkspace,
    StealthTransferInstruction,
    WorkspaceOffsetId,
)

if TYPE_CHECKING:
    from ootle._transaction_builder import TransactionBuilder


def _remap_arg(arg: InstructionArg, *, offset: int) -> InstructionArg:
    if isinstance(arg, InstructionArgWorkspace):
        ws = arg.workspace
        return InstructionArgWorkspace(WorkspaceOffsetId(id=ws.id + offset, offset=ws.offset))
    return arg


def _remap_instruction(instr: Instruction, *, offset: int, blob_offset: int) -> Instruction:
    if isinstance(instr, PublishTemplate) and blob_offset:
        return PublishTemplate(binary=instr.binary + blob_offset, metadata_hash=instr.metadata_hash)
    if offset == 0:
        return instr
    return _remap_workspace_refs(instr, offset=offset)


def _remap_workspace_refs(instr: Instruction, *, offset: int) -> Instruction:
    """Offset every workspace id an instruction carries (assumes ``offset != 0``)."""
    if isinstance(instr, PutLastInstructionOutputOnWorkspace):
        return PutLastInstructionOutputOnWorkspace(key=instr.key + offset)
    if isinstance(instr, CallMethod):
        call = instr.call
        if isinstance(call, ComponentRefWorkspace):
            call = ComponentRefWorkspace(workspace_id=call.workspace_id + offset)
        return CallMethod(
            call=call,
            method=instr.method,
            args=tuple(_remap_arg(a, offset=offset) for a in instr.args),
        )
    if isinstance(instr, CallFunction):
        return CallFunction(
            template_address=instr.template_address,
            function=instr.function,
            args=tuple(_remap_arg(a, offset=offset) for a in instr.args),
        )
    if isinstance(instr, StealthTransferInstruction):
        return _remap_stealth_transfer(instr, offset=offset)
    return instr


def _remap_stealth_transfer(
    instr: StealthTransferInstruction, *, offset: int
) -> StealthTransferInstruction:
    bucket = instr.revealed_input_bucket
    if bucket is None:
        return instr
    return StealthTransferInstruction(
        resource=instr.resource,
        statement=instr.statement,
        revealed_input_bucket=WorkspaceOffsetId(id=bucket.id + offset, offset=bucket.offset),
    )


def _merge_workspace_ids(dst_ws: dict[str, int], src_ws: dict[str, int], *, offset: int) -> None:
    """Fold *src_ws* into *dst_ws*, offsetting each id by *offset*."""
    for label, wid in src_ws.items():
        dst_ws.setdefault(label, wid + offset)


def merge_into(dst: TransactionBuilder, src: TransactionBuilder) -> None:
    """Merge *src*'s state into *dst*, remapping workspace ids to avoid conflicts.

    Private fields of both builders are aliased into locals up front so the
    rest of the function operates on plain aliases.
    """
    # Aliases below deliberately reach into TransactionBuilder internals; the
    # alternative is duplicating the merge inside the class and overflowing
    # the 200-line cap on ``_transaction_builder.py``.
    dst_ws, dst_body, dst_fee = dst._workspace_ids, dst._body, dst._fee  # pyright: ignore[reportPrivateUsage]  # internal access
    src_ws, src_body, src_fee = src._workspace_ids, src._body, src._fee  # pyright: ignore[reportPrivateUsage]  # internal access
    offset, blob_offset = len(dst_ws), len(dst_body.blobs)
    _merge_workspace_ids(dst_ws, src_ws, offset=offset)
    dst_body.instructions.extend(
        _remap_instruction(i, offset=offset, blob_offset=blob_offset) for i in src_body.instructions
    )
    dst_fee.instructions.extend(
        _remap_instruction(i, offset=offset, blob_offset=blob_offset) for i in src_fee.instructions
    )
    for req in src_body.inputs:
        dst_body.add_input(req)
    for req in src_fee.inputs:
        dst_fee.add_input(req)
    for blob in src_body.blobs:
        dst_body.add_blob(blob)


def merge_fee_builder(dst: TransactionBuilder, inner: TransactionBuilder) -> None:
    """Merge *inner*'s body into *dst*'s fee block, remapping workspace ids.

    The inner builder allocates workspace ids from 0; *dst* may already use
    some, so every workspace id carried in the appended instructions (and the
    label→id map) is offset by ``len(dst._workspace_ids)`` — the same scheme
    :func:`merge_into` uses. Blobs are folded onto the main body so blob-index
    references stay valid.
    """
    dst_ws, dst_body, dst_fee = dst._workspace_ids, dst._body, dst._fee  # pyright: ignore[reportPrivateUsage]  # internal access
    inner_ws, inner_body = inner._workspace_ids, inner._body  # pyright: ignore[reportPrivateUsage]  # internal access
    offset, blob_offset = len(dst_ws), len(dst_body.blobs)
    _merge_workspace_ids(dst_ws, inner_ws, offset=offset)
    dst_fee.instructions.extend(
        _remap_instruction(i, offset=offset, blob_offset=blob_offset)
        for i in inner_body.instructions
    )
    for req in inner_body.inputs:
        dst_fee.add_input(req)
    for blob in inner_body.blobs:
        dst_body.add_blob(blob)
