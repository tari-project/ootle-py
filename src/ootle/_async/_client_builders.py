"""Builder shortcut methods for :class:`AsyncOotleClient`.

Extracted into a sibling mixin so ``client.py`` stays under the
200-line ceiling. Each method is a one-line delegation to the
corresponding builder class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ootle._async.builders import IAsyncAccount, IAsyncComponent, IAsyncFaucet
    from ootle._async.client import AsyncOotleClient


def make_account(client: AsyncOotleClient) -> IAsyncAccount:
    """Build a new account transaction (sugar for ``IAsyncAccount(client)``)."""
    from ootle._async.builders import IAsyncAccount  # noqa: PLC0415

    return IAsyncAccount(client)


def make_faucet(client: AsyncOotleClient) -> IAsyncFaucet:
    """Build a new public-faucet transaction (sugar for ``IAsyncFaucet(client)``)."""
    from ootle._async.builders import IAsyncFaucet  # noqa: PLC0415

    return IAsyncFaucet(client)


def make_component(client: AsyncOotleClient) -> IAsyncComponent:
    """Build a new component transaction (sugar for ``IAsyncComponent(client)``)."""
    from ootle._async.builders import IAsyncComponent  # noqa: PLC0415

    return IAsyncComponent(client)
