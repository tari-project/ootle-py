"""Implementation of :meth:`TransactionBuilder.build_unsigned`.

Lives in its own module so ``_transaction_builder.py`` stays comfortably
under the 200-line cap, mirroring ``_transaction_builder_merge.py``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ootle._types._tx_body import UnsignedTransactionV1Body
from ootle._types.transaction import UnsignedTransaction

if TYPE_CHECKING:
    from ootle._transaction_builder import TransactionBuilder


def build_unsigned(builder: TransactionBuilder) -> UnsignedTransaction:
    """Finalise *builder* into an :class:`UnsignedTransaction`.

    Folds the fee block's inputs onto the merged body so fee inputs travel
    with the transaction's substate requirements.
    """
    body, fee = builder._body, builder._fee  # pyright: ignore[reportPrivateUsage]  # internal access
    merged = UnsignedTransactionV1Body(
        network=body.network,
        fee_instructions=list(fee.instructions),
        instructions=list(body.instructions),
        inputs=list(body.inputs),
        min_epoch=body.min_epoch,
        max_epoch=body.max_epoch,
        is_seal_signer_authorized=body.is_seal_signer_authorized,
        dry_run=body.dry_run,
        blobs=list(body.blobs),
    )
    for req in fee.inputs:
        merged.add_input(req)
    return UnsignedTransaction(json=json.dumps(merged.to_json()))
