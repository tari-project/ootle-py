"""``WantInput`` — the discriminated union of input-resolution requests.

Mirrors Rust's tagged enum via a namespace class plus three nested
frozen-slots dataclasses. Members are hashable so callers can hold a
``set[WantInput.*]`` for deduplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ootle._types.address import ComponentAddress, ResourceAddress
    from ootle._types.substate import SubstateId


class WantInput:
    """Namespace for the three want-input variants.

    Use a ``match`` statement to deconstruct::

        match want:
            case WantInput.VaultForResource(component=c, resource=r):
                ...
            case WantInput.SpecificSubstate(id=i):
                ...
            case WantInput.AllComponentVaults(component=c):
                ...
    """

    @dataclass(frozen=True, slots=True)
    class VaultForResource:
        """Resolve the vault on ``component`` for the given ``resource``."""

        component: ComponentAddress
        resource: ResourceAddress
        required: bool = True

    @dataclass(frozen=True, slots=True)
    class SpecificSubstate:
        """Resolve a single substate by id."""

        id: SubstateId
        required: bool = True

    @dataclass(frozen=True, slots=True)
    class AllComponentVaults:
        """Resolve every vault attached to the given component."""

        component: ComponentAddress

    @dataclass(frozen=True, slots=True)
    class StealthCommitment:
        """Declare a stealth UTXO (by 32-byte commitment) as a transaction input.

        The resolver derives the on-chain ``UtxoAddress``
        (``utxo_<resource>_<commitment>``) and adds it to the transaction's
        inputs (unversioned) so the engine can lock and DOWN it while executing
        the ``StealthTransfer`` instruction — see
        :func:`ootle._async._resolver_helpers.resolve_stealth_commitment` and
        Rust ``crates/wallet/ootle-rs/src/stealth/builder.rs``. The stealth
        authorizer separately fetches the same substate to hydrate the balance
        proof.
        """

        commitment: bytes
        resource: ResourceAddress
        required: bool = True
