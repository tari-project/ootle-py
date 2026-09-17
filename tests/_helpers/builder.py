"""Helpers for driving :class:`TransactionBuilder` directly in tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final, cast

if TYPE_CHECKING:
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.transaction import UnsignedTransaction

TEST_MAX_EPOCH: Final[int] = 11
"""Validity bound stamped by tests that build an envelope without ``prepare()``.

``max_epoch`` is mandatory on the wire and normally resolved from the live
network epoch inside ``prepare()``; tests that bypass ``prepare()`` to inspect
the raw envelope need a deterministic stand-in.
"""


def build_unsigned(builder: TransactionBuilder) -> UnsignedTransaction:
    """Build *builder*, defaulting ``max_epoch`` to :data:`TEST_MAX_EPOCH`."""
    if builder.max_epoch is None:
        builder.with_max_epoch(TEST_MAX_EPOCH)
    return builder.build_unsigned()


def build_body(builder: TransactionBuilder) -> dict[str, Any]:
    """Build *builder* and return the decoded ``UnsignedTransactionV1`` JSON."""
    return cast("dict[str, Any]", json.loads(build_unsigned(builder).json))
