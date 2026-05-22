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

    @classmethod
    def empty(cls, network: int) -> Self:
        """Return an empty body for the given network byte."""
        return cls(network=network, fee_instructions=[], instructions=[], inputs=[])

    def to_json(self) -> dict[str, Any]:
        """Serialize to the ``UnsignedTransactionV1`` JSON wire format."""
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
