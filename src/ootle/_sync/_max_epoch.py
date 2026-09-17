"""Default a builder's ``max_epoch`` from the live network epoch.

``UnsignedTransactionV1.max_epoch`` is mandatory — every transaction carries a
bounded validity window. Callers who do not pin one explicitly get
``current_epoch + DEFAULT_MAX_EPOCH_WINDOW``, resolved with a single
``GET network`` round-trip at ``prepare()`` time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle._types._tx_body import DEFAULT_MAX_EPOCH_WINDOW

if TYPE_CHECKING:
    from ootle._sync.client import OotleClient
    from ootle._transaction_builder import TransactionBuilder


def ensure_max_epoch(client: OotleClient, builder: TransactionBuilder) -> None:
    """Fill in *builder*'s ``max_epoch`` from the indexer unless already set."""
    if builder.max_epoch is not None:
        return
    epoch = client.get_epoch()
    builder.with_max_epoch(epoch + DEFAULT_MAX_EPOCH_WINDOW)
