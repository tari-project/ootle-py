"""Fee-payment helpers for :class:`TransactionBuilder`.

Lives in its own module so ``_transaction_builder.py`` stays comfortably
under the 200-line cap, mirroring ``_transaction_builder_merge.py`` and
``_transaction_builder_build.py``. Each helper appends a ``pay_fee``
instruction to the builder's fee block in place; the public methods on
``TransactionBuilder`` wrap them and return ``self`` for chaining.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle._types.address import ComponentAddress
from ootle._types.instructions import (
    CallMethod,
    ComponentRefAddress,
    ComponentRefWorkspace,
    PayFeeFromBucket,
    amount_literal,
)

if TYPE_CHECKING:
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.amount import Amount


def pay_fee_from_component(
    builder: TransactionBuilder,
    component: ComponentAddress | str,
    max_fee: Amount | int,
) -> None:
    """Append ``CallMethod(component, "pay_fee", [amount])`` to the fee block."""
    ref = ComponentRefAddress(address=ComponentAddress(str(component)))
    builder._fee.instructions.append(  # pyright: ignore[reportPrivateUsage]  # internal access
        CallMethod(call=ref, method="pay_fee", args=(amount_literal(max_fee),))
    )


def pay_fee_from_workspace_component(
    builder: TransactionBuilder,
    workspace_label: str,
    max_fee: Amount | int,
) -> None:
    """Pay fee from a workspace-bucket component (fee block)."""
    workspace_id = builder._resolve_workspace(workspace_label)  # pyright: ignore[reportPrivateUsage]  # internal access
    ref = ComponentRefWorkspace(workspace_id=workspace_id)
    builder._fee.instructions.append(  # pyright: ignore[reportPrivateUsage]  # internal access
        CallMethod(call=ref, method="pay_fee", args=(amount_literal(max_fee),))
    )


def pay_fee_from_bucket(builder: TransactionBuilder, bucket_label: str) -> None:
    """Append ``PayFeeFromBucket(bucket)`` to the fee block."""
    bucket = builder._resolve_workspace_offset(bucket_label)  # pyright: ignore[reportPrivateUsage]  # internal access
    builder._fee.instructions.append(  # pyright: ignore[reportPrivateUsage]  # internal access
        PayFeeFromBucket(bucket=bucket)
    )
