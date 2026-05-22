"""Faucet stealth-claim helpers — extracted from ``builders/faucet.py``.

Mirrors Rust ``FaucetInvokeBuilder::into_stealth_transfer``
(``crates/wallet/ootle-rs/src/builtin_templates/faucet.rs:105-135``):
after the public-faucet ``take_faucet_funds`` lands the dispensed
amount on an account workspace, this helper withdraws the revealed
amount from that workspace, hands it to a
:class:`StealthTransferInstruction`, and (optionally) routes fees
through the residual revealed-output bucket.

These live in the ``_async/stealth/`` subtree (which is hand-maintained
during the stealth workstream — see ``scripts/unasync.py``) so that
extending the faucet builder for stealth doesn't drag stealth-only
behaviour into the auto-generated ``_sync/builders/`` mirror.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ResourceAddress
from ootle._types.instructions import (
    CallMethod,
    ComponentRefWorkspace,
    PayFeeFromBucket,
    PutLastInstructionOutputOnWorkspace,
    StealthTransferInstruction,
    WorkspaceOffsetId,
    amount_literal,
    resource_address_literal,
)
from ootle._types.substate import SubstateId
from ootle._types.want_input import WantInput
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._async.builders._base import WantInputItem
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.stealth import StealthTransferStatement


_TARI_RESOURCE: ResourceAddress = ResourceAddress(TARI_TOKEN)


def apply_take_funds_stealth(
    builder: TransactionBuilder,
    want_list: set[WantInputItem],
    account_label: str | None,
    statement: StealthTransferStatement,
    *,
    pay_fees_from_revealed: bool,
    bucket_label: str,
    fee_bucket_label: str,
) -> None:
    """Extend the faucet's fee-instruction chain with a stealth claim.

    Pre-condition: :meth:`IAsyncFaucet.take_funds` (or
    :meth:`take_max_funds`) was already called so the account workspace
    label is set.

    Post-condition: a withdraw → workspace-put → stealth-transfer
    sequence is appended to the fee block, with the revealed-amount
    bucket wired into the :class:`StealthTransferInstruction`.

    The chain is appended onto the outer builder's shared fee block via
    :meth:`~TransactionBuilder.add_fee_instruction` and
    :meth:`~TransactionBuilder.alloc_workspace` rather than through
    :meth:`TransactionBuilder.with_fee_instructions_builder`. That helper
    builds in a fresh inner builder and offsets every workspace id on
    merge to dodge collisions — but this chain re-references the account
    workspace produced by ``take_funds`` (id ``account_wid``), and the
    offset would silently rewrite that back-reference. Allocating on the
    outer builder's own registry keeps the ids contiguous and the
    references intact (matching Rust's persistent fee-instruction
    builder, which shares one workspace-name registry across blocks).
    """
    if account_label is None:
        msg = "call take_funds() before take_funds_stealth() — no account workspace"
        raise InvalidArgumentError(msg)
    revealed_amount = statement.inputs_statement.revealed_amount
    if revealed_amount <= 0:
        msg = "take_funds_stealth requires the statement's revealed_amount to be positive"
        raise InvalidArgumentError(msg)
    _add_stealth_input_wants(want_list, statement)
    account_wid = builder._resolve_workspace(account_label)  # pyright: ignore[reportPrivateUsage]  # internal access

    builder.add_fee_instruction(
        CallMethod(
            call=ComponentRefWorkspace(workspace_id=account_wid),
            method="withdraw",
            args=(resource_address_literal(_TARI_RESOURCE), amount_literal(revealed_amount)),
        )
    )
    # bucket_label/fee_bucket_label are prefix-namespaced by _next_label, so they
    # never collide with account_label on the shared registry.
    bucket_wid = builder.alloc_workspace(bucket_label)
    builder.add_fee_instruction(PutLastInstructionOutputOnWorkspace(key=bucket_wid))
    builder.add_fee_instruction(
        StealthTransferInstruction(
            resource=_TARI_RESOURCE,
            statement=statement,
            revealed_input_bucket=WorkspaceOffsetId(id=bucket_wid),
        )
    )
    if pay_fees_from_revealed:
        _route_fees_through_revealed(builder, fee_bucket_label)


def _add_stealth_input_wants(
    want_list: set[WantInputItem], statement: StealthTransferStatement
) -> None:
    for sin in statement.inputs_statement.inputs:
        want_list.add(
            WantInput.StealthCommitment(commitment=sin.commitment, resource=_TARI_RESOURCE)
        )
        want_list.add(
            WantInput.SpecificSubstate(
                id=SubstateId(
                    opaque=f"utxo_{str(_TARI_RESOURCE).removeprefix('resource_')}_{sin.commitment.hex()}"
                ),
                required=True,
            )
        )


def _route_fees_through_revealed(builder: TransactionBuilder, label: str) -> None:
    """Emit the ``and_pay_fee_from_revealed_output`` chain.

    Mirrors Rust ``and_pay_fee_from_revealed_output``: the residual
    revealed-output bucket left by the stealth transfer lands on the
    workspace under ``label`` and the fee block draws ``PayFeeFromBucket``
    against it. Both instructions append onto the outer builder's shared
    fee block via :meth:`~TransactionBuilder.add_fee_instruction`,
    continuing the contiguous workspace-id run set up by
    :func:`apply_take_funds_stealth`.
    """
    wid = builder.alloc_workspace(label)
    builder.add_fee_instruction(PutLastInstructionOutputOnWorkspace(key=wid))
    builder.add_fee_instruction(PayFeeFromBucket(bucket=WorkspaceOffsetId(id=wid)))
