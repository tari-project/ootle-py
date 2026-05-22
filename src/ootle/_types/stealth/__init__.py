"""Stealth value types — pure data, no I/O.

This is the data layer for the stealth-transfer workstream. Builders,
authorizers, and the crypto provider all consume these types but live
elsewhere. None of the public exports here touch crypto or perform
network I/O — that work belongs to the transport and crypto layers.

Re-exports the public surface so ``from ootle._types.stealth import …``
works regardless of which sibling module actually defines a name. The
public-package surface (``ootle.__init__``) is *not* updated here — that
is deferred to step 06 once the user-facing API is firmed up.
"""

from __future__ import annotations

from ootle._types.stealth._proofs import (
    BalanceProofSignature,
    ViewableBalanceProof,
)
from ootle._types.stealth._substate_utxo import (
    ElgamalVerifiableBalance,
    StealthOutputBody,
)
from ootle._types.stealth._unspent import (
    StealthUnspentOutput,
    UnspentOutput,
)
from ootle._types.stealth.encrypted_data import (
    DecryptedData,
    EncryptedData,
)
from ootle._types.stealth.one_time_pubkey import OneTimePublicKey
from ootle._types.stealth.output import Mask, Output, positive_amount
from ootle._types.stealth.requirements import (
    SignatureRequirements,
    StealthSignerRequirement,
)
from ootle._types.stealth.statements import (
    StealthInput,
    StealthInputsStatement,
    StealthOutputsStatement,
    StealthTransferStatement,
)

__all__ = [
    "BalanceProofSignature",
    "DecryptedData",
    "ElgamalVerifiableBalance",
    "EncryptedData",
    "Mask",
    "OneTimePublicKey",
    "Output",
    "SignatureRequirements",
    "StealthInput",
    "StealthInputsStatement",
    "StealthOutputBody",
    "StealthOutputsStatement",
    "StealthSignerRequirement",
    "StealthTransferStatement",
    "StealthUnspentOutput",
    "UnspentOutput",
    "ViewableBalanceProof",
    "positive_amount",
]
