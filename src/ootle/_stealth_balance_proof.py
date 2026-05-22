"""Shared balance-proof helpers for stealth transfers.

Pure, synchronous functions shared by the async authorizer
(:mod:`ootle._async.stealth.authorizer`, which offloads the crypto call onto a
worker thread) and the faucet stealth path
(:func:`ootle._wallet_stealth.generate_outputs_statement`, which is sync). They
live outside the ``_async`` tree so the sync wallet path can reuse them without
an unasync round-trip; the crypto call itself is synchronous behind the WASM
lock (callers in async contexts wrap it in ``offload``).

Mirrors the balance-proof half of Rust ``StealthTransfer::prepare``
(:file:`crates/wallet/ootle-rs/src/stealth/builder.rs`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ootle._types.stealth import BalanceProofSignature
from ootle._types.stealth._json import dumps_stable
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._crypto._stealth_provider import StealthCryptoProvider
    from ootle._types.stealth import Mask, StealthInputsStatement, StealthOutputsStatement


_BALANCE_PROOF_LEN = 64


def compact_statement_json(payload: dict[str, Any]) -> str:
    """Encode a balance-proof statement dict via the canonical stable encoder.

    The WASM ``generateStealthBalanceProofSignature`` export ``serde_json``-
    re-parses these strings before hashing, so key order is wire-irrelevant.
    Routing through :func:`dumps_stable` (sorted keys) keeps a single stable
    encoder and pins the output against dataclass field reorders.
    """
    return dumps_stable(payload).decode("utf-8")


def split_balance_proof_bytes(raw: bytes) -> BalanceProofSignature:
    """Split a 64-byte flat signature into ``(public_nonce, signature)``."""
    if len(raw) != _BALANCE_PROOF_LEN:
        msg = f"balance proof signature must be {_BALANCE_PROOF_LEN} bytes, got {len(raw)}"
        raise InvalidArgumentError(msg)
    return BalanceProofSignature(public_nonce=raw[:32], signature=raw[32:])


def sign_balance_proof(
    crypto: StealthCryptoProvider,
    *,
    input_mask: Mask,
    output_mask: Mask,
    inputs_statement: StealthInputsStatement,
    outputs_statement: StealthOutputsStatement,
) -> BalanceProofSignature:
    """Sign the ``inputs == outputs`` balance proof for a stealth transfer.

    Synchronous: invokes :meth:`StealthCryptoProvider.generate_balance_proof_signature`
    directly. Async callers offload this whole call onto a worker thread.
    """
    raw = crypto.generate_balance_proof_signature(
        input_mask=input_mask,
        output_mask=output_mask,
        inputs_statement_json=compact_statement_json(inputs_statement.to_json()),
        outputs_statement_json=compact_statement_json(outputs_statement.to_json()),
    )
    return split_balance_proof_bytes(raw)
