"""``max_epoch`` / ``nonce`` envelope handling on :class:`TransactionBuilder`."""

from __future__ import annotations

import pytest

from ootle import TransactionBuilder
from ootle.errors import InvalidArgumentError
from tests._helpers.builder import build_body


def test_build_without_max_epoch_raises() -> None:
    """``max_epoch`` is mandatory on the wire, so an unset bound fails loudly."""
    builder = TransactionBuilder(0)
    assert builder.max_epoch is None
    with pytest.raises(InvalidArgumentError, match="max_epoch is required"):
        builder.build_unsigned()


def test_with_max_epoch_is_reflected_in_the_envelope() -> None:
    body = build_body(TransactionBuilder(0).with_max_epoch(42))
    assert body["max_epoch"] == 42


def test_nonce_defaults_to_zero_and_is_settable() -> None:
    assert build_body(TransactionBuilder(0))["nonce"] == 0
    assert build_body(TransactionBuilder(0).with_nonce(7))["nonce"] == 7


def test_min_epoch_round_trips() -> None:
    body = build_body(TransactionBuilder(0).with_min_epoch(3))
    assert body["min_epoch"] == 3
