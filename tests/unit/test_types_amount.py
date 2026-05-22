"""Amount value type and the ``TARI`` constant."""

from __future__ import annotations

from ootle._types.amount import TARI, Amount


def test_tari_constant_matches_microtari_unit() -> None:
    assert TARI == 1_000_000


def test_amount_is_int() -> None:
    a = Amount(42)
    assert isinstance(a, int)
    assert a == 42


def test_amount_arithmetic_returns_int() -> None:
    a = Amount(2)
    b = Amount(3)
    assert a + b == 5
    assert a * 4 == 8


def test_amount_repr_redacts_namespace() -> None:
    assert repr(Amount(7)) == "Amount(7)"


def test_amount_can_be_built_from_tari_constant() -> None:
    assert Amount(2 * TARI) == 2_000_000
