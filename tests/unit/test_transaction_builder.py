"""``TransactionBuilder`` tests — JSON-shape goldens + workspace plumbing."""

from __future__ import annotations

import json

import pytest

from ootle import TransactionBuilder
from ootle._types._tari_constants import (
    XTR_FAUCET_COMPONENT_ADDRESS,
    XTR_FAUCET_VAULT_ADDRESS,
)
from ootle._types.amount import TARI, Amount
from ootle._types.network import Network
from ootle._types.substate import SubstateId, SubstateRequirement
from ootle.errors import InvalidArgumentError


def test_empty_builder_emits_minimal_envelope() -> None:
    body = json.loads(TransactionBuilder(Network.LOCAL_NET).build_unsigned().json)
    assert body["network"] == 0x10
    assert body["fee_instructions"] == []
    assert body["instructions"] == []
    assert body["inputs"] == []
    assert body["is_seal_signer_authorized"] is True
    assert body["dry_run"] is False


def test_call_method_emits_correct_shape() -> None:
    builder = TransactionBuilder(Network.LOCAL_NET).call_method("component_xyz", "method_name")
    body = json.loads(builder.build_unsigned().json)
    assert len(body["instructions"]) == 1
    instr = body["instructions"][0]
    assert "CallMethod" in instr
    assert instr["CallMethod"]["call"] == {"Address": "component_xyz"}
    assert instr["CallMethod"]["method"] == "method_name"
    assert instr["CallMethod"]["args"] == []


def test_pay_fee_from_component_lands_in_fee_block() -> None:
    body = json.loads(
        TransactionBuilder(0)
        .pay_fee_from_component("component_owner", Amount(500))
        .build_unsigned()
        .json
    )
    assert body["instructions"] == []
    assert len(body["fee_instructions"]) == 1
    fee = body["fee_instructions"][0]["CallMethod"]
    assert fee["method"] == "pay_fee"
    assert fee["call"] == {"Address": "component_owner"}


def test_workspace_label_resolution() -> None:
    builder = (
        TransactionBuilder(0)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("bucket_0")
        .call_method_on_workspace("bucket_0", "deposit")
    )
    body = json.loads(builder.build_unsigned().json)
    assert body["instructions"][1]["PutLastInstructionOutputOnWorkspace"]["key"] == 0
    deposit = body["instructions"][2]["CallMethod"]
    # `ComponentReference::Workspace(WorkspaceId)` — bare u16, not WorkspaceOffsetId.
    assert deposit["call"] == {"Workspace": 0}


def test_unknown_workspace_label_raises() -> None:
    builder = TransactionBuilder(0)
    with pytest.raises(InvalidArgumentError):
        builder.call_method_on_workspace("nope", "m")


def test_with_fee_instructions_builder_merges_into_fee_block() -> None:
    builder = TransactionBuilder(0).with_fee_instructions_builder(
        lambda b: b.call_method(XTR_FAUCET_COMPONENT_ADDRESS, "take").add_input(
            SubstateRequirement(id=SubstateId(XTR_FAUCET_VAULT_ADDRESS), version=None)
        )
    )
    body = json.loads(builder.build_unsigned().json)
    assert len(body["fee_instructions"]) == 1
    assert body["fee_instructions"][0]["CallMethod"]["call"] == {
        "Address": XTR_FAUCET_COMPONENT_ADDRESS
    }
    assert body["instructions"] == []
    assert any(req["substate_id"] == XTR_FAUCET_VAULT_ADDRESS for req in body["inputs"])


def test_with_fee_instructions_builder_remaps_colliding_workspace_id() -> None:
    """Body already owns slot 0; the fee builder's bucket must be offset to 1."""
    builder = (
        TransactionBuilder(0)
        .call_method("component_body", "take")
        .put_last_instruction_output_on_workspace("body_bucket")
        .with_fee_instructions_builder(
            lambda b: b.call_method(
                "component_fee", "take"
            ).put_last_instruction_output_on_workspace("fee_bucket")
        )
    )
    body = json.loads(builder.build_unsigned().json)
    body_key = body["instructions"][1]["PutLastInstructionOutputOnWorkspace"]["key"]
    fee_key = body["fee_instructions"][1]["PutLastInstructionOutputOnWorkspace"]["key"]
    assert body_key == 0
    assert fee_key == 1
    assert builder._workspace_ids == {"body_bucket": 0, "fee_bucket": 1}  # pyright: ignore[reportPrivateUsage]  # internal access


def test_with_fee_instructions_builder_remaps_workspace_referencing_call() -> None:
    """A workspace-referenced call inside the fee builder is offset alongside its bucket."""
    builder = (
        TransactionBuilder(0)
        .call_method("component_body", "take")
        .put_last_instruction_output_on_workspace("body_bucket")
        .with_fee_instructions_builder(
            lambda b: (
                b.call_method("component_fee", "take")
                .put_last_instruction_output_on_workspace("fee_bucket")
                .call_method_on_workspace("fee_bucket", "deposit")
            )
        )
    )
    body = json.loads(builder.build_unsigned().json)
    workspace_call = next(
        i["CallMethod"]["call"]
        for i in body["fee_instructions"]
        if isinstance(i.get("CallMethod", {}).get("call"), dict)
        and "Workspace" in i["CallMethod"]["call"]
    )
    assert workspace_call == {"Workspace": 1}


def test_create_account_emits_owner_pk_hex() -> None:
    pk = b"\xaa" * 32
    body = json.loads(
        TransactionBuilder(0)
        .call_method("component_a", "take")
        .put_last_instruction_output_on_workspace("bucket")
        .create_account(pk, bucket_workspace_label="bucket")
        .build_unsigned()
        .json
    )
    create = body["instructions"][2]["CreateAccount"]
    assert create["owner_public_key"] == "aa" * 32
    # CreateAccount.bucket_workspace_id is a WorkspaceOffsetId, not a bare WorkspaceId.
    assert create["bucket_workspace_id"] == {"id": 0, "offset": None}


def test_dry_run_flag_set() -> None:
    body = json.loads(TransactionBuilder(0).with_dry_run(True).build_unsigned().json)
    assert body["dry_run"] is True


def test_amount_literal_round_trip_in_pay_fee() -> None:
    body = json.loads(
        TransactionBuilder(0).pay_fee_from_component("c", 10 * TARI).build_unsigned().json
    )
    arg = body["fee_instructions"][0]["CallMethod"]["args"][0]
    assert "Literal" in arg
    body_bytes = bytes.fromhex(arg["Literal"])
    import cbor2  # noqa: PLC0415

    assert cbor2.loads(body_bytes) == [10 * TARI, 0]
