"""Coverage for ``TransactionBuilder.merge`` workspace + input remapping."""

from __future__ import annotations

import json

from ootle import TransactionBuilder
from ootle._types.network import Network
from ootle._types.substate import SubstateId, SubstateRequirement


def test_merge_remaps_workspace_ids_when_dst_already_has_buckets() -> None:
    """Workspace ids in src should be offset by the count already in dst."""
    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("dst_bucket")
    )
    src = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_b", "take")
        .put_last_instruction_output_on_workspace("src_bucket")
        .call_method_on_workspace("src_bucket", "deposit")
    )
    dst.merge(src)
    body = json.loads(dst.build_unsigned().json)
    # dst's bucket is at id 0; src's bucket should be remapped to id 1.
    keys = [
        i["PutLastInstructionOutputOnWorkspace"]["key"]
        for i in body["instructions"]
        if "PutLastInstructionOutputOnWorkspace" in i
    ]
    assert keys == [0, 1]
    workspace_calls = [
        i["CallMethod"]["call"]
        for i in body["instructions"]
        if "CallMethod" in i and isinstance(i["CallMethod"]["call"], dict)
    ]
    assert {"Workspace": 1} in workspace_calls


def test_merge_remaps_args_referencing_remapped_workspace() -> None:
    """A workspace-referenced ``InstructionArg`` survives the offset rewrite."""
    from ootle._types.instructions import (  # noqa: PLC0415
        InstructionArgWorkspace,
        WorkspaceOffsetId,
    )

    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_x", "x")
        .put_last_instruction_output_on_workspace("dst_buck")
    )
    src_b = TransactionBuilder(Network.LOCAL_NET)
    src_b.call_method("component_b", "take").put_last_instruction_output_on_workspace("src_buck")
    wid = src_b._workspace_ids["src_buck"]  # pyright: ignore[reportPrivateUsage]  # internal access
    src_b.call_method(
        "component_b",
        "consume",
        (InstructionArgWorkspace(WorkspaceOffsetId(id=wid)),),
    )
    dst.merge(src_b)
    body = json.loads(dst.build_unsigned().json)
    consume = next(
        i["CallMethod"]
        for i in body["instructions"]
        if i.get("CallMethod", {}).get("method") == "consume"
    )
    arg = consume["args"][0]
    # Original wid was 0; offset by len(dst._workspace_ids) (=1) → 1.
    assert arg["Workspace"]["id"] == 1


def test_merge_remaps_stealth_transfer_revealed_input_bucket() -> None:
    """A merged ``StealthTransferInstruction``'s revealed-input bucket is offset."""
    from ootle._types._tari_constants import TARI_TOKEN  # noqa: PLC0415
    from ootle._types.address import ResourceAddress  # noqa: PLC0415
    from ootle._types.instructions import (  # noqa: PLC0415
        StealthTransferInstruction,
        WorkspaceOffsetId,
    )
    from ootle._types.stealth import StealthTransferStatement  # noqa: PLC0415

    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_x", "x")
        .put_last_instruction_output_on_workspace("dst_buck")
    )
    src = TransactionBuilder(Network.LOCAL_NET)
    src.add_instruction(
        StealthTransferInstruction(
            resource=ResourceAddress(TARI_TOKEN),
            statement=StealthTransferStatement.revealed_only(100, 100),
            revealed_input_bucket=WorkspaceOffsetId(id=0),
        )
    )
    dst.merge(src)
    body = json.loads(dst.build_unsigned().json)
    transfer = next(i["StealthTransfer"] for i in body["instructions"] if "StealthTransfer" in i)
    # dst already holds one bucket (id 0) → offset 1 → src's ref 0 becomes 1.
    assert transfer["revealed_input_bucket"]["id"] == 1


def test_merge_carries_inputs_from_src() -> None:
    dst = TransactionBuilder(Network.LOCAL_NET)
    req = SubstateRequirement(id=SubstateId("component_carried"), version=None)
    src = TransactionBuilder(Network.LOCAL_NET).add_input(req)
    dst.merge(src)
    body = json.loads(dst.build_unsigned().json)
    assert any(i["substate_id"] == "component_carried" for i in body["inputs"])


def test_merge_no_offset_when_dst_empty() -> None:
    """Offset = 0 path: src is copied verbatim into a fresh dst."""
    dst = TransactionBuilder(Network.LOCAL_NET)
    src = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_b", "take")
        .put_last_instruction_output_on_workspace("solo")
    )
    dst.merge(src)
    body = json.loads(dst.build_unsigned().json)
    keys = [
        i["PutLastInstructionOutputOnWorkspace"]["key"]
        for i in body["instructions"]
        if "PutLastInstructionOutputOnWorkspace" in i
    ]
    assert keys == [0]
