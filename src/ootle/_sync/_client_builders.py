"""Builder shortcut methods for :class:`OotleClient`.

Extracted into a sibling mixin so ``client.py`` stays under the
200-line ceiling. Each method is a one-line delegation to the
corresponding builder class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ootle._sync.builders import IAccount, IComponent, IFaucet
    from ootle._sync.client import OotleClient


def make_account(client: OotleClient) -> IAccount:
    """Build a new account transaction (sugar for ``IAccount(client)``)."""
    from ootle._sync.builders import IAccount  # noqa: PLC0415

    return IAccount(client)


def make_faucet(client: OotleClient) -> IFaucet:
    """Build a new public-faucet transaction (sugar for ``IFaucet(client)``)."""
    from ootle._sync.builders import IFaucet  # noqa: PLC0415

    return IFaucet(client)


def make_component(client: OotleClient) -> IComponent:
    """Build a new component transaction (sugar for ``IComponent(client)``)."""
    from ootle._sync.builders import IComponent  # noqa: PLC0415

    return IComponent(client)
