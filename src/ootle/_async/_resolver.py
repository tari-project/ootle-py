"""``AsyncTransactionInputResolver`` — walks a want-list, fetches substates, folds inputs.

Mirrors Rust's ``provider/input_resolver.rs:56-91``. Fixed-point loop:
each pass either resolves wants from the cache or schedules new
substates to fetch in the next ``fetch_substates`` round-trip.

Inputs are folded back into the :class:`UnsignedTransaction` by parsing
the JSON payload, mutating ``inputs``, and re-serialising — see
:mod:`ootle._async._resolver_helpers`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ootle._async._resolver_helpers import (
    fold_inputs,
    resolve_all_vaults,
    resolve_specific,
    resolve_stealth_commitment,
    resolve_vault,
)
from ootle._types.want_input import WantInput
from ootle.errors import IndexerClientError

if TYPE_CHECKING:
    from ootle._async._transport import AsyncIndexerTransport
    from ootle._types.substate import Substate, SubstateId, SubstateRequirement
    from ootle._types.transaction import UnsignedTransaction


logger = logging.getLogger(__name__)

_WantItem = (
    WantInput.VaultForResource
    | WantInput.SpecificSubstate
    | WantInput.AllComponentVaults
    | WantInput.StealthCommitment
)


class AsyncTransactionInputResolver:
    """Resolves a ``set[WantInput]`` against the indexer + folds inputs into the tx."""

    __slots__ = ("_transport",)

    def __init__(self, transport: AsyncIndexerTransport) -> None:
        self._transport = transport

    async def resolve(
        self,
        unsigned: UnsignedTransaction,
        want_list: set[_WantItem],
    ) -> UnsignedTransaction:
        """Walk ``want_list`` and return a new :class:`UnsignedTransaction`.

        Empty want-list → returns ``unsigned`` unchanged. Required wants
        whose substates are missing raise :class:`IndexerClientError`.
        """
        if not want_list:
            return unsigned
        cache: dict[SubstateId, Substate] = {}
        missing: set[SubstateId] = set()
        wants = list(want_list)
        satisfied = [False] * len(wants)
        new_inputs: list[SubstateRequirement] = []
        while True:
            to_fetch: list[SubstateId] = []
            progress = False
            for i, want in enumerate(wants):
                if satisfied[i]:
                    continue
                if self._resolve_one(want, cache, missing, new_inputs, to_fetch):
                    satisfied[i] = True
                    progress = True
            if all(satisfied):
                break
            if not to_fetch and not progress:
                msg = "input resolver made no progress — outstanding wants cannot be satisfied"
                raise IndexerClientError(msg, status=None, body="", url=self._transport.url)
            if to_fetch:
                await self._cache_substates(to_fetch, cache, missing)
        return fold_inputs(unsigned, new_inputs)

    def _resolve_one(
        self,
        want: _WantItem,
        cache: dict[SubstateId, Substate],
        missing: set[SubstateId],
        new_inputs: list[SubstateRequirement],
        to_fetch: list[SubstateId],
    ) -> bool:
        match want:
            case WantInput.SpecificSubstate(id=sub_id, required=required):
                return resolve_specific(sub_id, required, cache, missing, new_inputs, to_fetch)
            case WantInput.VaultForResource(component=c, resource=r, required=required):
                return resolve_vault(c, r, required, cache, missing, new_inputs, to_fetch)
            case WantInput.AllComponentVaults(component=c):
                return resolve_all_vaults(c, cache, missing, new_inputs, to_fetch)
            case WantInput.StealthCommitment(commitment=commitment, resource=resource):
                return resolve_stealth_commitment(
                    commitment, resource, cache, missing, new_inputs, to_fetch
                )
            case _:
                msg = f"unhandled _WantItem variant: {want!r}"
                raise AssertionError(msg)

    async def _cache_substates(
        self,
        ids: list[SubstateId],
        cache: dict[SubstateId, Substate],
        missing: set[SubstateId],
    ) -> None:
        logger.debug("resolver fetching %d substate(s)", len(ids))
        fetched = await self._transport.fetch_substates(ids)
        cache.update(fetched)
        for sub_id in ids:
            if sub_id not in cache:
                missing.add(sub_id)
