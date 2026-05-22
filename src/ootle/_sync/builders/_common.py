"""``SyncUnsignedTransactionBuilder`` Protocol — every async builder fits this shape."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from ootle._types.address import Address
    from ootle._types.substate import SubstateRequirement
    from ootle._types.transaction import UnsignedTransaction


@runtime_checkable
class SyncUnsignedTransactionBuilder(Protocol):
    """Common shape for every async template-specific builder.

    Returned by ``client.faucet()``, ``client.account()`` (M5),
    ``client.component()`` (M6).
    """

    @property
    def default_signer_address(self) -> Address:
        """Address of the wallet's default signer.

        Raises:
            DefaultSignerNotSetError: If the wallet has no default signer.
        """
        ...

    def add_input(self, requirement: SubstateRequirement) -> Self:
        """Add a substate requirement to the transaction's inputs."""
        ...

    def prepare(self) -> UnsignedTransaction:
        """Resolve any pending want-list entries and emit an unsigned transaction."""
        ...
