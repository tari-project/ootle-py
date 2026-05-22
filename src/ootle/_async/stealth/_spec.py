"""``StealthTransferSpec`` — return value of :meth:`AsyncStealthTransfer.prepare`.

Pure-data carrier for the unsigned transaction, the provider-generated
stealth transfer statement, and the
:class:`~ootle._types.stealth.SignatureRequirements` shape the
authorizer consumes. :class:`StealthTransferSpec` is the contract
between the builder and the stealth authorizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ootle._async.stealth._builder_helpers import StealthTransferState
    from ootle._types.stealth import Mask, SignatureRequirements, StealthTransferStatement
    from ootle._types.transaction import UnsignedTransaction


@dataclass(frozen=True, slots=True)
class StealthTransferSpec:
    """Output of :meth:`AsyncStealthTransfer.prepare`.

    Attributes:
        unsigned: Assembled :class:`UnsignedTransaction` with stealth
            and (optional) fee instructions already folded in.
        statement: Provider-generated :class:`StealthTransferStatement`
            embedded as a literal arg in the transaction. Kept on the
            spec so the authorizer can re-inspect the balance proof
            without re-parsing the JSON envelope.
        signature_requirements: Per Rust ``SignatureRequirements`` —
            tells the stealth authorizer which signers must sign and
            whether the seal signer must be the account key.
        output_mask: Aggregated output mask the provider emitted alongside
            the outputs statement. Required by the authorizer to
            generate the balance-proof signature. ``None`` for a
            revealed-only transfer with no outputs.
        state: Builder-local accumulator (stealth inputs, resource,
            revealed amounts) preserved for the authorizer so it can
            re-derive the substate ids and signer ordering without
            re-parsing the assembled transaction body.
    """

    unsigned: UnsignedTransaction
    statement: StealthTransferStatement
    signature_requirements: SignatureRequirements
    output_mask: Mask | None
    state: StealthTransferState
