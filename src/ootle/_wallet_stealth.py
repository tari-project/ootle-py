"""Stealth read helpers exposed on :class:`OotleWallet`.

Kept in a sibling module so ``wallet.py`` stays under the 200-line
ceiling. The two helpers route through the wallet's configured
stealth :class:`~ootle._crypto._stealth_provider.StealthCryptoProvider`
(set via :class:`OotleWallet` ``crypto=`` ctor kwarg or
:meth:`OotleWallet.set_crypto`).

- :func:`decrypt_input_data` mirrors Rust ``WalletProvider::decrypt_input_data``
  — given a commitment and the encrypted blob from a stealth UTXO,
  return a :class:`DecryptedData` carrier with the mask + value.
- :func:`generate_outputs_statement` drives the public faucet stealth path
  (``IAsyncFaucet.take_funds_stealth``). It produces the output half via the
  provider's bulletproof + viewable-balance-proof pipeline, derives the
  matching revealed input (Σ stealth outputs + revealed output), and — since
  the faucet has no stealth inputs — signs the ``inputs == outputs`` balance
  proof inline with a zero input mask. This mirrors Rust
  ``StealthTransfer::prepare``, which returns a *complete* statement (with
  proof) before it is handed to ``IFaucet::into_stealth_transfer``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from ootle._crypto import ensure_stealth_capable
from ootle._stealth_balance_proof import sign_balance_proof
from ootle._types.stealth import (
    Mask,
    StealthInputsStatement,
    StealthTransferStatement,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._crypto._stealth_provider import StealthCryptoProvider
    from ootle._types.stealth import DecryptedData, EncryptedData, Output


_ZERO_INPUT_MASK = Mask(b"\x00" * 32)


def decrypt_input_data(
    crypto: object,
    commitment: bytes,
    encrypted_input: EncryptedData,
    *,
    sender_public_nonce: bytes,
    view_secret: bytes,
    skip_memo: bool = False,
) -> DecryptedData:
    """Decrypt the AEAD payload of a stealth UTXO this wallet owns.

    The body shape mirrors the ``unblind_output`` payload — a JSON dict
    carrying the encrypted blob, the commitment, and the sender's public
    nonce. The nonce is required: the provider derives the AEAD key from
    the Diffie-Hellman of ``view_secret`` and ``sender_public_nonce``, so
    omitting it makes the UTXO body unparseable. Surface a typed
    :class:`DecryptedData` to callers.
    """
    stealth = _require(crypto)
    body = json.dumps(
        {
            "commitment": commitment.hex(),
            "sender_public_nonce": sender_public_nonce.hex(),
            "encrypted_data": encrypted_input.to_json(),
            "minimum_value_promise": 0,
        }
    )
    return stealth.unblind_output(
        commitment=commitment,
        output_body_json=body,
        view_secret=view_secret,
        skip_memo=skip_memo,
    )


def generate_outputs_statement(
    crypto: object,
    specs: Sequence[Output],
    revealed: int,
) -> StealthTransferStatement:
    """Produce a complete :class:`StealthTransferStatement` for the faucet path.

    ``revealed`` is the revealed *output* amount (Rust's
    ``revealed_output_amount``) — typically the fee paid back through the
    revealed-output bucket. The revealed *input* is derived as the sum of the
    stealth output amounts plus that revealed output, so the transfer balances
    by construction. When there are stealth outputs the ``inputs == outputs``
    balance proof is signed inline (faucet claims carry no stealth inputs, so
    the input mask is the zero scalar) and the envelope is validated.
    """
    stealth = _require(crypto)
    if revealed <= 0 and not specs:
        msg = "generate_outputs_statement: need at least one output or a positive revealed amount"
        raise ValueError(msg)
    result = stealth.generate_outputs_statement(specs, revealed)
    revealed_input = sum(o.amount for o in specs) + revealed
    inputs_statement = StealthInputsStatement.new_revealed_only(revealed_input)
    balance_proof = None
    if result.statement.outputs:
        balance_proof = sign_balance_proof(
            stealth,
            input_mask=_ZERO_INPUT_MASK,
            output_mask=result.output_mask,
            inputs_statement=inputs_statement,
            outputs_statement=result.statement,
        )
    statement = StealthTransferStatement(
        inputs_statement=inputs_statement,
        outputs_statement=result.statement,
        balance_proof=balance_proof,
    )
    if balance_proof is not None:
        stealth.validate_transfer(statement)
    return statement


def _require(crypto: object) -> StealthCryptoProvider:
    """Resolve the wallet's stealth provider, defaulting to the WASM bridge."""
    return cast("StealthCryptoProvider", ensure_stealth_capable(crypto))
