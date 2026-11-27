"""Regression tests for workspace slot tracking across ``TransactionBuilder.merge``."""

from __future__ import annotations

from typing import Any

from ootle import TransactionBuilder
from ootle._types.instructions import PutLastInstructionOutputOnWorkspace
from ootle._types.network import Network
from tests._helpers.builder import build_body


def _put_keys(instructions: list[dict[str, Any]]) -> list[int]:
    return [
        i["PutLastInstructionOutputOnWorkspace"]["key"]
        for i in instructions
        if "PutLastInstructionOutputOnWorkspace" in i
    ]


def _workspace_calls(instructions: list[dict[str, Any]]) -> list[int]:
    return [
        i["CallMethod"]["call"]["Workspace"]
        for i in instructions
        if "CallMethod" in i
        and isinstance(i["CallMethod"]["call"], dict)
        and "Workspace" in i["CallMethod"]["call"]
    ]


def test_merge_shared_labels_produces_distinct_workspace_slots() -> None:
    """Repeated merges with the same label must still advance the slot counter."""
    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("bucket")
    )
    src1 = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_b", "take")
        .put_last_instruction_output_on_workspace("bucket")
        .call_method_on_workspace("bucket", "deposit")
    )
    src2 = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_c", "take")
        .put_last_instruction_output_on_workspace("bucket")
        .call_method_on_workspace("bucket", "deposit")
    )

    dst.merge(src1).merge(src2)
    dst.call_method("component_d", "take").put_last_instruction_output_on_workspace("next")

    body = build_body(dst)
    assert _put_keys(body["instructions"]) == [0, 1, 2, 3]
    assert _workspace_calls(body["instructions"]) == [1, 2]
    assert dst.next_workspace_id() == 4
    assert dst._workspace_ids == {"bucket": 0, "next": 3}  # pyright: ignore[reportPrivateUsage]  # internal access


def test_merge_shared_and_new_labels_keep_registry_consistent() -> None:
    """Existing labels keep dst's slot while new labels adopt the offset slot."""
    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("bucket")
    )
    src = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_b", "take")
        .put_last_instruction_output_on_workspace("bucket")
        .call_method("component_c", "take")
        .put_last_instruction_output_on_workspace("extra")
        .call_method_on_workspace("extra", "use")
    )

    dst.merge(src)
    dst.call_method("component_d", "take").put_last_instruction_output_on_workspace("after")

    body = build_body(dst)
    assert _put_keys(body["instructions"]) == [0, 1, 2, 3]
    assert _workspace_calls(body["instructions"]) == [2]
    assert dst.next_workspace_id() == 4
    assert dst._workspace_ids == {"bucket": 0, "extra": 2, "after": 3}  # pyright: ignore[reportPrivateUsage]  # internal access


def test_manual_put_instruction_advances_workspace_counter() -> None:
    """Manual ``PutLastInstructionOutputOnWorkspace`` keys advance ``next_workspace_id``."""
    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .add_instruction(PutLastInstructionOutputOnWorkspace(key=2))
        .add_instruction(PutLastInstructionOutputOnWorkspace(key=1))
    )
    assert dst.next_workspace_id() == 3

    dst.put_last_instruction_output_on_workspace("after_manual")
    assert dst.next_workspace_id() == 4

    src = (
        TransactionBuilder(Network.LOCAL_NET)
        .add_instruction(PutLastInstructionOutputOnWorkspace(key=0))
        .put_last_instruction_output_on_workspace("src_lbl")
    )
    dst.merge(src)
    assert dst.next_workspace_id() == 6

    dst.put_last_instruction_output_on_workspace("final")
    body = build_body(dst)
    assert _put_keys(body["instructions"]) == [2, 1, 3, 4, 5, 6]
    assert dst.next_workspace_id() == 7
    assert dst._workspace_ids == {"after_manual": 3, "src_lbl": 5, "final": 6}  # pyright: ignore[reportPrivateUsage]  # internal access


def test_fee_builder_merge_avoids_collisions_across_shared_and_manual_slots() -> None:
    """``merge_fee_builder`` offsets past shared labels and manual fee puts."""
    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("bucket")
        .add_fee_instruction(PutLastInstructionOutputOnWorkspace(key=1))
        .with_fee_instructions_builder(
            lambda f: (
                f.call_method("component_fee_1", "take")
                .put_last_instruction_output_on_workspace("bucket")
                .call_method_on_workspace("bucket", "deposit")
            )
        )
        .with_fee_instructions_builder(
            lambda f: (
                f.call_method("component_fee_2", "take")
                .put_last_instruction_output_on_workspace("bucket")
                .call_method("component_fee_3", "take")
                .put_last_instruction_output_on_workspace("fee_extra")
            )
        )
        .call_method("component_end", "take")
        .put_last_instruction_output_on_workspace("next")
    )

    body = build_body(dst)
    assert _put_keys(body["instructions"]) == [0, 5]
    assert _put_keys(body["fee_instructions"]) == [1, 2, 3, 4]
    assert _workspace_calls(body["fee_instructions"]) == [2]
    assert dst.next_workspace_id() == 6
    assert dst._workspace_ids == {"bucket": 0, "fee_extra": 4, "next": 5}  # pyright: ignore[reportPrivateUsage]  # internal access


def test_merge_into_includes_src_fee_workspace_slots() -> None:
    """Merging a builder that already owns fee workspaces reserves those slots too."""
    dst = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("bucket")
    )
    src = (
        TransactionBuilder(Network.LOCAL_NET)
        .call_method("component_b", "take")
        .put_last_instruction_output_on_workspace("bucket")
        .with_fee_instructions_builder(
            lambda f: f.call_method(
                "component_fee", "take"
            ).put_last_instruction_output_on_workspace("fee_bucket")
        )
    )

    dst.merge(src).put_last_instruction_output_on_workspace("next")
    body = build_body(dst)
    assert _put_keys(body["instructions"]) == [0, 1, 3]
    assert _put_keys(body["fee_instructions"]) == [2]
    assert dst.next_workspace_id() == 4
    assert dst._workspace_ids == {"bucket": 0, "fee_bucket": 2, "next": 3}  # pyright: ignore[reportPrivateUsage]  # internal access
