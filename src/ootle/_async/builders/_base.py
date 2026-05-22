"""``BuilderBase`` mixin shared by every async template builder.

Holds:

- the attached client (read-only — the builder calls back into it for
  the wallet's default signer and the resolver),
- a :class:`TransactionBuilder` instance (the actual instruction
  accumulator — fully sync; produces JSON), and
- a ``set[WantInput]`` that the resolver walks at ``prepare()`` time.

The class itself is public so subclasses (``IAsyncFaucet``, future
``IAsyncAccount`` / ``IAsyncComponent``) can inherit it; the ``_``
prefix on attributes is the convention for builder-internal state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._transaction_builder import TransactionBuilder
from ootle._types.want_input import WantInput
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._async.client import AsyncOotleClient
    from ootle._types.address import Address
    from ootle._types.substate import SubstateRequirement
    from ootle._types.transaction import UnsignedTransaction


WantInputItem = (
    WantInput.VaultForResource
    | WantInput.SpecificSubstate
    | WantInput.AllComponentVaults
    | WantInput.StealthCommitment
)


class BuilderBase:
    """Shared state for :class:`IAsyncFaucet` and future template builders.

    Subclasses access ``self._builder`` to emit instructions and
    ``self._want_list`` to register input requirements that the
    resolver will satisfy at ``prepare()`` time.
    """

    __slots__ = ("_builder", "_client", "_want_list")

    def __init__(self, client: AsyncOotleClient) -> None:
        self._client = client
        self._builder = TransactionBuilder(client.network)
        self._want_list: set[WantInputItem] = set()

    @property
    def default_signer_address(self) -> Address:
        """Address of the wallet's default signer.

        Raises:
            DefaultSignerNotSetError: If the wallet has no default signer.
            InvalidArgumentError: If the client has no wallet attached.
        """
        wallet = self._client.wallet
        if wallet is None:
            msg = "client has no wallet attached — cannot resolve default signer"
            raise InvalidArgumentError(msg)
        return wallet.default_address

    def add_input(self, requirement: SubstateRequirement) -> Self:
        """Add a substate requirement to the transaction's inputs."""
        self._builder.add_input(requirement)
        return self

    async def prepare(self) -> UnsignedTransaction:
        """Default ``prepare()`` — builds + resolves the want-list.

        Subclasses can override if they need to do work after the
        builder has emitted but before the resolver runs.
        """
        unsigned = self._builder.build_unsigned()
        return await self._client.resolver.resolve(unsigned, self._want_list)
