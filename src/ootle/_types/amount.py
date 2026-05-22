"""``Amount`` value type and the ``TARI`` µTari constant.

``Amount`` subclasses ``int`` so that arithmetic stays ergonomic
(``2 * TARI`` is a plain Python expression) while still being a distinct
nominal type for pyright.
"""

from __future__ import annotations

from typing import Final, override

TARI: Final[int] = 1_000_000
"""µTari per 1 TARI."""


class Amount(int):
    """A µTari quantity.

    1 TARI = 1_000_000 µTari. ``Amount`` inherits from ``int`` so that
    operators like ``+``/``-``/``*`` work without ceremony; the result
    of those operators is a plain ``int``, which is intentional —
    callers cast back to ``Amount`` only when handing values to typed
    APIs that demand it.
    """

    __slots__ = ()

    @override
    def __repr__(self) -> str:
        return f"Amount({int(self)})"
