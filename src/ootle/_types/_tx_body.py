"""``UnsignedTransactionV1Body`` — mutable accumulator for transaction JSON.

Extracted from ``_types/instructions.py`` to keep both modules under the
200-line limit; re-exported from there for backward compatibility.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from ootle._types.instructions import Instruction
    from ootle._types.substate import SubstateId, SubstateRequirement

_MAX_BLOBS = 256

DEFAULT_MAX_EPOCH_WINDOW = 10
"""Epochs past the current one that client-side builders grant a transaction by default.

Mirrors the window the ``ootle-rs`` docs use (``get_epoch() + 10``). ``max_epoch`` is
mandatory on ``UnsignedTransactionV1``, so a builder with no explicit bound resolves
one from the live network epoch at ``prepare()`` time.
"""


def substate_requirement_to_json(req: SubstateRequirement) -> dict[str, Any]:
    """Render a :class:`SubstateRequirement` into its wire JSON form."""
    return {"substate_id": req.id.opaque, "version": req.version}


@dataclass(slots=True)
class FeeBlock:
    """Accumulator for the fee-instruction sub-block of a transaction.

    Carries only the fields the fee block actually uses on the wire
    (``fee_instructions`` and any additional ``inputs`` they imply); the
    epoch bounds, ``dry_run``, ``blobs``, etc. live on the main body only.
    """

    instructions: list[Instruction] = field(default_factory=list["Instruction"])
    inputs: list[SubstateRequirement] = field(default_factory=list["SubstateRequirement"])

    def add_input(self, req: SubstateRequirement) -> None:
        """Append ``req`` if not already present (deduplicates by equality)."""
        if all(req != existing for existing in self.inputs):
            self.inputs.append(req)


@dataclass(slots=True)
class UnsignedTransactionV1Body:
    """Mutable accumulator that serializes to ``UnsignedTransactionV1`` JSON."""

    network: int
    fee_instructions: list[Instruction]
    instructions: list[Instruction]
    inputs: list[SubstateRequirement]
    min_epoch: int | None = None
    max_epoch: int | None = None
    is_seal_signer_authorized: bool = True
    dry_run: bool = False
    blobs: list[bytes] = field(default_factory=list[bytes])
    nonce: int = 0

    @classmethod
    def empty(cls, network: int) -> Self:
        """Return an empty body for the given network byte."""
        return cls(network=network, fee_instructions=[], instructions=[], inputs=[])

    def to_json(self) -> dict[str, Any]:
        """Serialize to the ``UnsignedTransactionV1`` JSON wire format.

        Raises:
            InvalidArgumentError: ``max_epoch`` has not been set. The engine
                requires every transaction to carry a bounded validity window
                — set it with ``TransactionBuilder.with_max_epoch()``, or let
                an async builder's ``prepare()`` default it from the live epoch.
        """
        if self.max_epoch is None:
            from ootle.errors import InvalidArgumentError  # noqa: PLC0415

            msg = (
                "max_epoch is required — call TransactionBuilder.with_max_epoch(epoch) "
                "(e.g. await client.get_epoch() + DEFAULT_MAX_EPOCH_WINDOW)"
            )
            raise InvalidArgumentError(msg)
        return {
            "network": self.network,
            "fee_instructions": [i.to_json() for i in self.fee_instructions],
            "instructions": [i.to_json() for i in self.instructions],
            "inputs": [substate_requirement_to_json(r) for r in self.inputs],
            "min_epoch": self.min_epoch,
            "max_epoch": self.max_epoch,
            "is_seal_signer_authorized": self.is_seal_signer_authorized,
            "dry_run": self.dry_run,
            "blobs": [base64.b64encode(b).decode() for b in self.blobs],
            "nonce": self.nonce,
        }

    def add_blob(self, blob: bytes) -> int:
        """Append ``blob`` and return its assigned ``BlobIndex`` (0-based, u8)."""
        if len(self.blobs) >= _MAX_BLOBS:
            from ootle.errors import InvalidArgumentError  # noqa: PLC0415

            msg = f"transaction blob count would exceed the BlobIndex range ({_MAX_BLOBS} max)"
            raise InvalidArgumentError(msg)
        idx = len(self.blobs)
        self.blobs.append(blob)
        return idx

    def add_input(self, req: SubstateRequirement) -> None:
        """Append ``req`` if not already present (deduplicates by equality)."""
        if all(req != existing for existing in self.inputs):
            self.inputs.append(req)


def substate_id_to_unversioned_requirement(sub_id: SubstateId) -> SubstateRequirement:
    """Wrap an unversioned :class:`SubstateId` as a :class:`SubstateRequirement`."""
    from ootle._types.substate import SubstateRequirement  # noqa: PLC0415

    return SubstateRequirement(id=sub_id, version=None)
