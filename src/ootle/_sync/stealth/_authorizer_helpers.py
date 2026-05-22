"""Helpers for :class:`WalletStealthAuthorizer`.

Split out of ``authorizer.py`` so both files stay under the 200-line
ceiling. The helpers are pure functions / small dataclasses — the
authorizer composes them.

Responsibilities, in the order the Rust ``StealthTransfer::prepare`` runs
them (:file:`crates/wallet/ootle-rs/src/stealth/builder.rs::prepare`):

1. Map each stealth-input commitment to a UTXO substate id.
2. Fetch the substates and read each ``public_nonce``/``encrypted_data``.
3. Decrypt each input mask via :meth:`StealthCryptoProvider.unblind_output`
   and sum them via :meth:`StealthCryptoProvider.aggregate_input_masks`.
4. Sign the balance proof via :meth:`StealthCryptoProvider.generate_balance_proof_signature`.
5. Patch the :class:`StealthTransferInstruction` in the unsigned-tx JSON
   so it carries the hydrated :class:`StealthTransferStatement`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from ootle._sync._client_stealth_parse import parse_substate_utxo
from ootle._sync._offload import offload
from ootle._types.stealth import (
    Mask,
    SignatureRequirements,
    StealthSignerRequirement,
    StealthTransferStatement,
    UnspentOutput,
)
from ootle._types.substate import SubstateId
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._sync.client import OotleClient
    from ootle._crypto._stealth_provider import SyncStealthCryptoProvider
    from ootle._types.address import Address, ResourceAddress
    from ootle._types.substate import Substate


_AGG_INPUT_MASK_LEN = 32


@dataclass(frozen=True, slots=True)
class InputResolution:
    """Output of :func:`fetch_stealth_input_bodies`."""

    required_signers: tuple[StealthSignerRequirement, ...]
    agg_input_mask: Mask


def utxo_substate_id(resource: ResourceAddress, commitment: bytes) -> SubstateId:
    """Mirror Rust ``UtxoAddress::new(resource, commitment).to_string()``."""
    resource_hex = str(resource).removeprefix("resource_")
    return SubstateId(opaque=f"utxo_{resource_hex}_{commitment.hex()}")


def fetch_stealth_input_bodies(
    client: OotleClient,
    resource: ResourceAddress,
    inputs: Sequence[tuple[Address, bytes]],
    crypto: SyncStealthCryptoProvider,
    view_secret: bytes,
) -> InputResolution:
    """Resolve every stealth input to its public-nonce and decrypted mask.

    Mirrors the loop in Rust ``StealthTransfer::prepare`` over
    ``found_substates``: each input's mask is decrypted via
    :meth:`StealthCryptoProvider.unblind_output`, then the per-input
    masks are summed into one aggregated input mask via
    :meth:`StealthCryptoProvider.aggregate_input_masks` (a pure-WASM
    Ristretto scalar sum). A single input reduces to its mask
    unchanged; an empty input set yields the zero mask.
    """
    if not inputs:
        return InputResolution(
            required_signers=(), agg_input_mask=Mask(b"\x00" * _AGG_INPUT_MASK_LEN)
        )
    required: list[StealthSignerRequirement] = []
    masks: list[Mask] = []
    for addr, commitment in inputs:
        sub_id = utxo_substate_id(resource, commitment)
        substate = client.fetch_substate(sub_id)
        if substate is None:
            msg = f"stealth input {sub_id.opaque} not found on indexer"
            raise InvalidArgumentError(msg)
        output = _unspent_output_for(substate, commitment)
        required.append(
            StealthSignerRequirement(signer=addr, public_nonce=output.sender_public_nonce)
        )
        decrypted = offload(
            partial(
                crypto.unblind_output,
                commitment=commitment,
                output_body_json=json.dumps(output.to_json()),
                view_secret=view_secret,
                skip_memo=True,
            )
        )
        masks.append(Mask(decrypted.mask))
    agg = crypto.aggregate_input_masks(masks)
    return InputResolution(required_signers=tuple(required), agg_input_mask=agg)


def _unspent_output_for(substate: Substate, commitment: bytes) -> UnspentOutput:
    """Rebuild the send-side :class:`UnspentOutput` for a fetched stealth input.

    The indexer returns the engine ``Utxo`` substate, whose ``OutputBody``
    carries a ``public_nonce`` and **no** commitment (it is derived and lives
    in the substate id — see :func:`parse_substate_utxo`). We pair that body
    with the commitment the caller already holds to feed
    :meth:`StealthCryptoProvider.unblind_output`, which needs only the nonce,
    encrypted data, and commitment for the AEAD owner-read.
    """
    parsed = parse_substate_utxo(substate)
    if parsed is None:
        msg = f"stealth input {substate.id.opaque} is burnt or not a parseable UTXO"
        raise InvalidArgumentError(msg)
    _, body = parsed
    return UnspentOutput(
        commitment=commitment,
        sender_public_nonce=body.public_nonce,
        encrypted_data=body.encrypted_data,
        minimum_value_promise=body.minimum_value_promise,
    )


def patch_stealth_statement(
    unsigned_json: str,
    new_statement: StealthTransferStatement,
) -> str:
    """Replace the (sole) ``StealthTransfer.statement`` in ``unsigned_json``."""
    body: object = json.loads(unsigned_json)
    if not isinstance(body, dict):
        msg = "unsigned transaction JSON must be an object"
        raise InvalidArgumentError(msg)
    instructions = cast("dict[str, Any]", body).get("instructions")
    if not isinstance(instructions, list):
        msg = "unsigned transaction has no instructions list"
        raise InvalidArgumentError(msg)
    found = False
    for ins in cast("list[Any]", instructions):
        if not isinstance(ins, dict):
            continue
        st = cast("dict[str, Any]", ins).get("StealthTransfer")
        if isinstance(st, dict):
            cast("dict[str, Any]", st)["statement"] = new_statement.to_json()
            found = True
            break
    if not found:
        msg = "no StealthTransfer instruction found in unsigned transaction"
        raise InvalidArgumentError(msg)
    return json.dumps(body)


def build_signature_requirements(
    must_sign_with_account_key: bool,
    required: Sequence[StealthSignerRequirement],
) -> SignatureRequirements:
    """Mirror the Rust branch at ``builder.rs::prepare`` lines 193-197."""
    if must_sign_with_account_key:
        return SignatureRequirements.new_must_sign_with_account_key(required)
    # When no account-key signature is required, the first stealth
    # signer is implicitly the seal signer — same as Rust.
    return SignatureRequirements.new_opt_with_seal_signer(required, None)
