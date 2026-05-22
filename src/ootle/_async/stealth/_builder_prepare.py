"""Terminal :meth:`AsyncStealthTransfer.prepare` flow.

Split out of ``transfer.py`` so the builder file stays under the
200-line ceiling and the prepare step is unit-testable in isolation
(the seam between local instruction emission, the stealth crypto call,
and resolver fold-in).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ootle._async._offload import offload
from ootle._async.stealth._builder_helpers import (
    emit_revealed_output_deposit,
    emit_stealth_transfer_instruction,
    validate_state,
)
from ootle._async.stealth._spec import StealthTransferSpec
from ootle._crypto import ensure_stealth_capable
from ootle._crypto._stealth_provider import StealthOutputsStatementResult
from ootle._types.instructions import WorkspaceOffsetId
from ootle._types.stealth import (
    SignatureRequirements,
    StealthInputsStatement,
    StealthTransferStatement,
)
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._async.builders._base import WantInputItem
    from ootle._async.client import AsyncOotleClient
    from ootle._async.stealth._builder_helpers import StealthTransferState
    from ootle._crypto._stealth_provider import StealthCryptoProvider
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.address import ComponentAddress


async def prepare_stealth_transfer(
    *,
    client: AsyncOotleClient,
    builder: TransactionBuilder,
    want_list: set[WantInputItem],
    state: StealthTransferState,
    revealed_input_label: str | None,
) -> StealthTransferSpec:
    """Run validation, stealth crypto, instruction emission, and resolver fold."""
    validate_state(state)
    outputs_result = await _call_outputs_statement(client, state)
    statement = StealthTransferStatement(
        inputs_statement=StealthInputsStatement(
            inputs=tuple(state.inputs_to_spend.values()),
            revealed_amount=state.revealed_input_amount,
        ),
        outputs_statement=outputs_result.statement,
        balance_proof=None,
    )
    revealed_bucket: WorkspaceOffsetId | None = None
    if revealed_input_label is not None:
        wid: int = builder._resolve_workspace(revealed_input_label)  # pyright: ignore[reportPrivateUsage]  # internal access
        revealed_bucket = WorkspaceOffsetId(id=wid)
    emit_stealth_transfer_instruction(builder, state.resource, statement, revealed_bucket)
    if state.revealed_output_amount > 0:
        emit_revealed_output_deposit(builder, want_list, _signer_account(client), state.resource)
    unsigned = builder.build_unsigned()
    unsigned = await client.resolver.resolve(unsigned, want_list)
    return StealthTransferSpec(
        unsigned=unsigned,
        statement=statement,
        signature_requirements=_derive_signature_requirements(state),
        output_mask=outputs_result.output_mask if outputs_result.statement.outputs else None,
        state=state,
    )


async def _call_outputs_statement(
    client: AsyncOotleClient,
    state: StealthTransferState,
) -> StealthOutputsStatementResult:
    """Dispatch ``generate_outputs_statement`` via the stealth crypto provider.

    The provider defaults to the singleton WASM bridge when the client
    has no explicit ``crypto=``. A non-stealth provider raises
    :class:`InvalidArgumentError`.
    """
    stealth = cast(
        "StealthCryptoProvider",
        ensure_stealth_capable(client._crypto),  # pyright: ignore[reportPrivateUsage]  # internal access
    )
    result = await offload(
        lambda: stealth.generate_outputs_statement(
            tuple(state.outputs), state.revealed_output_amount
        )
    )
    if not isinstance(result, StealthOutputsStatementResult):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard against non-conforming providers
        msg = (
            "configured CryptoProvider returned a non-StealthOutputsStatementResult "
            f"from generate_outputs_statement: {type(result).__name__}"
        )
        raise InvalidArgumentError(msg)
    return result


def _derive_signature_requirements(state: StealthTransferState) -> SignatureRequirements:
    """Derive :class:`SignatureRequirements` from purely-local builder state.

    Step 05's authorizer enriches this with the on-chain public nonces
    fetched per stealth input — see ``builder.rs::prepare`` for the
    full Rust derivation. The local view captures only the
    ``must_sign_with_account_key`` flag and leaves ``required_signers``
    empty. The account key must sign whenever the signer's account is
    spent from: a revealed-input withdrawal or a ``pay_fee_from_revealed``
    (both draw on the account vault).
    """
    if state.revealed_input_amount > 0 or state.fee_from_revealed:
        return SignatureRequirements.new_must_sign_with_account_key(())
    return SignatureRequirements.new_opt_with_seal_signer((), None)


def _signer_account(client: AsyncOotleClient) -> ComponentAddress:
    """Resolve the wallet's default account — the revealed-output deposit target."""
    wallet = client.wallet
    if wallet is None:
        msg = "client has no wallet — cannot deposit the stealth revealed output"
        raise InvalidArgumentError(msg)
    return wallet.default_address.to_component_address()
