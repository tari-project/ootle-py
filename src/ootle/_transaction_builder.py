"""Low-level synchronous builder for ``UnsignedTransactionV1`` JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._transaction_builder_build import build_unsigned
from ootle._transaction_builder_fees import (
    pay_fee_from_bucket,
    pay_fee_from_component,
    pay_fee_from_workspace_component,
)
from ootle._transaction_builder_merge import merge_fee_builder, merge_into
from ootle._types._tx_body import FeeBlock, UnsignedTransactionV1Body
from ootle._types.address import ComponentAddress
from ootle._types.instructions import (
    CallMethod,
    ComponentRefAddress,
    ComponentRefWorkspace,
    CreateAccount,
    InstructionArg,
    PublishTemplate,
    PutLastInstructionOutputOnWorkspace,
    WorkspaceOffsetId,
)
from ootle._types.network import Network
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ootle._types.amount import Amount
    from ootle._types.instructions import Instruction
    from ootle._types.substate import SubstateRequirement
    from ootle._types.transaction import UnsignedTransaction


class TransactionBuilder:
    """Fluent builder for :class:`UnsignedTransaction`."""

    __slots__ = ("_body", "_fee", "_workspace_ids")

    def __init__(self, network: Network | int) -> None:
        net_byte = network.value if isinstance(network, Network) else int(network)
        self._body = UnsignedTransactionV1Body.empty(net_byte)
        self._fee = FeeBlock()
        self._workspace_ids: dict[str, int] = {}

    def next_workspace_id(self) -> int:
        """Return the next free workspace id without allocating it."""
        return len(self._workspace_ids)

    def _alloc_workspace(self, label: str) -> int:
        if label in self._workspace_ids:
            msg = f"workspace label {label!r} already allocated"
            raise InvalidArgumentError(msg)
        wid = self.next_workspace_id()
        self._workspace_ids[label] = wid
        return wid

    def _resolve_workspace(self, label: str) -> int:
        wid = self._workspace_ids.get(label)
        if wid is None:
            msg = f"no workspace label named {label!r} has been defined"
            raise InvalidArgumentError(msg)
        return wid

    def _resolve_workspace_offset(self, label: str) -> WorkspaceOffsetId:
        return WorkspaceOffsetId(id=self._resolve_workspace(label))

    def call_method(
        self,
        component: ComponentAddress | str,
        method: str,
        args: Sequence[InstructionArg] = (),
    ) -> Self:
        """Append ``CallMethod`` targeting a component address."""
        ref = ComponentRefAddress(address=ComponentAddress(str(component)))
        self._body.instructions.append(CallMethod(call=ref, method=method, args=tuple(args)))
        return self

    def call_method_on_workspace(
        self,
        workspace_label: str,
        method: str,
        args: Sequence[InstructionArg] = (),
    ) -> Self:
        """Append ``CallMethod`` targeting a workspace bucket."""
        ref = ComponentRefWorkspace(workspace_id=self._resolve_workspace(workspace_label))
        self._body.instructions.append(CallMethod(call=ref, method=method, args=tuple(args)))
        return self

    def create_account(
        self, owner_public_key: bytes, bucket_workspace_label: str | None = None
    ) -> Self:
        """Append ``CreateAccount`` (idempotent on-chain)."""
        label = bucket_workspace_label
        bucket = self._resolve_workspace_offset(label) if label is not None else None
        ins = CreateAccount(owner_public_key=owner_public_key, bucket_workspace_id=bucket)
        self._body.instructions.append(ins)
        return self

    def put_last_instruction_output_on_workspace(self, label: str) -> Self:
        """Save the last instruction's output to a named workspace bucket."""
        wid = self._alloc_workspace(label)
        self._body.instructions.append(PutLastInstructionOutputOnWorkspace(key=wid))
        return self

    def add_input(self, requirement: SubstateRequirement) -> Self:
        """Add a substate requirement to the transaction's inputs."""
        self._body.add_input(requirement)
        return self

    def add_instruction(self, instruction: Instruction) -> Self:
        """Append a pre-built ``Instruction`` variant to the body."""
        self._body.instructions.append(instruction)
        return self

    def pay_fee_from_component(
        self,
        component: ComponentAddress | str,
        max_fee: Amount | int,
    ) -> Self:
        """Append ``CallMethod(component, "pay_fee", [amount])`` to the fee block."""
        pay_fee_from_component(self, component, max_fee)
        return self

    def pay_fee_from_workspace_component(self, workspace_label: str, max_fee: Amount | int) -> Self:
        """Pay fee from a workspace-bucket component (fee block)."""
        pay_fee_from_workspace_component(self, workspace_label, max_fee)
        return self

    def pay_fee_from_bucket(self, bucket_label: str) -> Self:
        """Append ``PayFeeFromBucket(bucket)`` to the fee block."""
        pay_fee_from_bucket(self, bucket_label)
        return self

    def with_fee_instructions_builder(self, f: Callable[[Self], Self]) -> Self:
        """Build fee instructions inside ``f``; merges its output into the fee block.

        Workspace ids in the inner builder are offset to avoid colliding with
        any already allocated on ``self`` — see :func:`merge_fee_builder`.
        """
        inner = type(self)(self._body.network)
        f(inner)
        merge_fee_builder(self, inner)
        return self

    def with_dry_run(self, dry_run: bool) -> Self:
        """Set the ``dry_run`` flag on the unsigned transaction."""
        self._body.dry_run = dry_run
        return self

    def with_min_epoch(self, epoch: int | None) -> Self:
        """Set the minimum epoch the transaction is valid in."""
        self._body.min_epoch = epoch
        return self

    def with_max_epoch(self, epoch: int | None) -> Self:
        """Set the maximum epoch the transaction is valid in."""
        self._body.max_epoch = epoch
        return self

    def then(self, f: Callable[[Self], Self]) -> Self:
        """Apply ``f`` to ``self`` (sugar for chained conditionals)."""
        return f(self)

    def merge(self, other: TransactionBuilder) -> Self:
        """Merge *other*'s state into *self*, remapping workspace ids and blob refs."""
        merge_into(self, other)
        return self

    def publish_template(self, blob: bytes) -> Self:
        """Register ``blob`` and append ``PublishTemplate`` referencing it by index."""
        idx = self._body.add_blob(blob)
        self._body.instructions.append(PublishTemplate(binary=idx))
        return self

    def build_unsigned(self) -> UnsignedTransaction:
        """Finalise into a :class:`UnsignedTransaction`."""
        return build_unsigned(self)
