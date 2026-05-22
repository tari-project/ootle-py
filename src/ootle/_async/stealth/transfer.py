"""``AsyncStealthTransfer`` — confidential-transfer builder.

Mirrors Rust ``crates/wallet/ootle-rs/src/stealth/builder.rs::StealthTransfer``
and TypeScript ``packages/ootle/src/stealth-transfer.ts`` — state
accumulates through chained ``spend_*`` / ``to_*`` calls, then
:meth:`prepare` asks the stealth crypto provider to generate the
:class:`StealthOutputsStatement`, assembles the
:class:`StealthTransferStatement`, emits the
:class:`StealthTransferInstruction`, and folds inputs via the
resolver.

Stealth crypto (bulletproofs, balance proofs) is delegated to the
configured :class:`~ootle._crypto.CryptoProvider`, which defaults to
the singleton WASM bridge. A ``crypto=`` that does not implement the
stealth surface makes :meth:`prepare` raise
:class:`~ootle.errors.InvalidArgumentError`.

Construct via the user-facing builder helper added in Step 06; for
now, instantiate directly::

    spec = await (
        AsyncStealthTransfer(client, TARI_TOKEN)
        .spend_revealed_input(account, 2_000)
        .to_revealed_output(500)
        .to_stealth_output(Output(recipient, TARI_TOKEN, 1_500))
        .pay_fee_from_revealed(amount=100)
        .prepare()
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._async.stealth._builder_helpers import (
    StealthTransferState,
    add_stealth_input_want,
    ensure_positive,
)
from ootle._async.stealth._builder_prepare import prepare_stealth_transfer
from ootle._transaction_builder import TransactionBuilder
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ResourceAddress
from ootle._types.instructions import amount_literal, resource_address_literal
from ootle._types.stealth import StealthInput
from ootle._types.substate import SubstateId
from ootle._types.want_input import WantInput
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable

    from ootle._async.builders._base import WantInputItem
    from ootle._async.client import AsyncOotleClient
    from ootle._async.stealth._spec import StealthTransferSpec
    from ootle._types.address import Address, ComponentAddress
    from ootle._types.amount import Amount
    from ootle._types.stealth import Output


class AsyncStealthTransfer:
    """Stealth-transfer builder. Construct directly or via Step 06's client method.

    Tracks resource, stealth inputs, revealed amounts on both sides,
    and stealth outputs in the same ordered shape Rust's
    ``StealthTransferSpec`` uses. Composes with the existing
    :class:`TransactionBuilder` for fee binding and revealed-bucket
    withdrawals; the dedicated :class:`StealthTransferInstruction`
    carries the confidential payload.
    """

    __slots__ = (
        "_builder",
        "_client",
        "_label_counter",
        "_revealed_input_label",
        "_state",
        "_want_list",
    )

    def __init__(self, client: AsyncOotleClient, resource: ResourceAddress) -> None:
        self._client = client
        self._builder = TransactionBuilder(client.network)
        self._want_list: set[WantInputItem] = set()
        self._state = StealthTransferState(resource=resource)
        self._revealed_input_label: str | None = None
        self._label_counter = 0

    @property
    def default_signer_address(self) -> Address:
        """Address of the wallet's default signer."""
        wallet = self._client.wallet
        if wallet is None:
            msg = "client has no wallet attached — cannot resolve default signer"
            raise InvalidArgumentError(msg)
        return wallet.default_address

    # ----- state accumulation -------------------------------------------

    def spend_stealth_input(self, owner_addr: Address, commitment: bytes) -> Self:
        """Spend a stealth UTXO owned by ``owner_addr`` (32-byte commitment)."""
        if owner_addr in self._state.inputs_to_spend:
            msg = f"stealth input from {owner_addr.bech32m} already added"
            raise InvalidArgumentError(msg)
        self._state.inputs_to_spend[owner_addr] = StealthInput(commitment=commitment)
        add_stealth_input_want(self._want_list, commitment, self._state.resource)
        return self

    def spend_revealed_input(self, component: ComponentAddress, amount: Amount | int) -> Self:
        """Withdraw ``amount`` from ``component``'s revealed vault into the transfer.

        A stealth transfer carries a single revealed-input bucket (matching
        Rust's ``StealthTransfer``); calling this twice would strand the first
        withdrawn bucket, so a second call is rejected.
        """
        if self._revealed_input_label is not None:
            msg = "spend_revealed_input may be called once; use spend_stealth_input for more inputs"
            raise InvalidArgumentError(msg)
        positive = ensure_positive(int(amount), label="spend_revealed_input amount")
        self._state.revealed_input_amount += positive
        label = self._next_label("RevealedStealthIn")
        self._want_list.add(
            WantInput.VaultForResource(
                component=component, resource=self._state.resource, required=True
            )
        )
        self._want_list.add(WantInput.SpecificSubstate(id=SubstateId(opaque=str(component))))
        (
            self._builder.call_method(
                component,
                "withdraw",
                (resource_address_literal(self._state.resource), amount_literal(positive)),
            ).put_last_instruction_output_on_workspace(label)
        )
        self._revealed_input_label = label
        return self

    def to_stealth_output(self, output: Output) -> Self:
        """Add a stealth recipient (mirrors Rust ``to_stealth_output``)."""
        self._state.outputs.append(output)
        return self

    def to_revealed_output(self, amount: Amount | int) -> Self:
        """Accumulate ``amount`` into the revealed-output bucket."""
        self._state.revealed_output_amount += ensure_positive(
            int(amount), label="to_revealed_output amount"
        )
        return self

    def pay_fee_from_revealed(self, amount: Amount | int) -> Self:
        """Pay fees from the transfer's revealed output.

        The fee counts toward the revealed-output side of the balance
        (``∑inputs == ∑outputs``) and is charged from the signer's account
        when :meth:`prepare` deposits the revealed-output bucket back into
        it (refunding any unused fee).
        """
        positive = ensure_positive(int(amount), label="pay_fee_from_revealed amount")
        self._state.revealed_output_amount += positive
        self._state.fee_from_revealed = True
        signer = self.default_signer_address
        account = signer.to_component_address()
        self._want_list.add(
            WantInput.VaultForResource(
                component=account, resource=ResourceAddress(TARI_TOKEN), required=True
            )
        )
        self._want_list.add(WantInput.SpecificSubstate(id=SubstateId(opaque=str(account))))
        self._builder.pay_fee_from_component(account, positive)
        return self

    def pay_fee_from_stealth(self, component: ComponentAddress, amount: Amount | int) -> Self:
        """Pay fees from a stealth account's revealed bucket."""
        self._want_list.add(WantInput.SpecificSubstate(id=SubstateId(opaque=str(component))))
        self._builder.pay_fee_from_component(component, amount)
        return self

    def with_builder(self, fn: Callable[[TransactionBuilder], TransactionBuilder]) -> Self:
        """Escape hatch — mutate the underlying ``TransactionBuilder``."""
        fn(self._builder)
        return self

    # ----- terminal -----------------------------------------------------

    async def prepare(self) -> StealthTransferSpec:
        """Generate the transfer statement, emit instructions, resolve inputs."""
        return await prepare_stealth_transfer(
            client=self._client,
            builder=self._builder,
            want_list=self._want_list,
            state=self._state,
            revealed_input_label=self._revealed_input_label,
        )

    def _next_label(self, prefix: str) -> str:
        label = f"__{prefix}_{self._label_counter}"
        self._label_counter += 1
        return label
