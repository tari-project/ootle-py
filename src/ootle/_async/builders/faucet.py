"""``IAsyncFaucet`` — public-path XTR faucet builder.

Mirrors Rust's ``builtin_templates::faucet::IFaucet``. The public path
ships in v1; the stealth path (:meth:`take_funds_stealth`) delegates
to ``_async/stealth/faucet_path.py`` so the stealth-specific glue
stays out of the unasync-generated ``_sync/builders/`` mirror.

Typical usage::

    unsigned = await client.faucet().take_funds().pay_fee(500).prepare()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._async.builders._base import BuilderBase
from ootle._types._tari_constants import (
    TARI_TOKEN,
    XTR_FAUCET_CLAIM_RESOURCE_ADDRESS,
    XTR_FAUCET_COMPONENT_ADDRESS,
    XTR_FAUCET_VAULT_ADDRESS,
)
from ootle._types.address import ResourceAddress
from ootle._types.instructions import InstructionArgWorkspace, WorkspaceOffsetId
from ootle._types.substate import SubstateId, SubstateRequirement
from ootle._types.want_input import WantInput

if TYPE_CHECKING:
    from ootle._async.client import AsyncOotleClient
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.amount import Amount
    from ootle._types.stealth import StealthTransferStatement


class IAsyncFaucet(BuilderBase):
    """Public-path faucet builder. Construct via ``client.faucet()``."""

    __slots__ = ("_account_workspace_label", "_label_counter")

    def __init__(self, client: AsyncOotleClient) -> None:
        super().__init__(client)
        self._account_workspace_label: str | None = None
        self._label_counter = 0

    def take_max_funds(self) -> Self:
        """Take the faucet's default dispensed amount into the signer's account."""
        return self.take_funds()

    def take_funds(self) -> Self:
        """Take funds from the public faucet and deposit into the signer's account.

        Mirrors Rust ``IFaucet::take_faucet_funds``. The dispensed amount is
        fixed by the on-chain faucet template.
        """
        signer = self.default_signer_address
        recipient_account = signer.to_component_address()
        account_label = self._next_label()
        self._want_list.add(
            WantInput.VaultForResource(
                component=recipient_account,
                resource=ResourceAddress(TARI_TOKEN),
                required=False,
            )
        )
        self._want_list.add(
            WantInput.SpecificSubstate(
                id=SubstateId(opaque=str(recipient_account)),
                required=False,
            )
        )
        owner_pk = signer.owner_pk

        def _build(b: TransactionBuilder) -> TransactionBuilder:
            faucet_req = SubstateRequirement(
                id=SubstateId(XTR_FAUCET_COMPONENT_ADDRESS), version=None
            )
            vault_req = SubstateRequirement(id=SubstateId(XTR_FAUCET_VAULT_ADDRESS), version=None)
            claim_req = SubstateRequirement(
                id=SubstateId(XTR_FAUCET_CLAIM_RESOURCE_ADDRESS), version=None
            )
            # Allocate the account workspace first, then resolve its id by label so
            # `take`'s argument references the id that
            # put_last_instruction_output_on_workspace actually assigned — rather than
            # predicting it via next_workspace_id() before allocation.
            b.create_account(owner_pk).put_last_instruction_output_on_workspace(account_label)
            account_wid = b._resolve_workspace(account_label)  # pyright: ignore[reportPrivateUsage]  # internal access
            ws_arg = InstructionArgWorkspace(WorkspaceOffsetId(id=account_wid))
            return (
                b.call_method(XTR_FAUCET_COMPONENT_ADDRESS, "take", (ws_arg,))
                .add_input(faucet_req)
                .add_input(vault_req)
                .add_input(claim_req)
            )

        self._builder.with_fee_instructions_builder(_build)
        self._account_workspace_label = account_label
        return self

    def pay_fee(self, amount: Amount | int) -> Self:
        """Charge ``amount`` of the taken funds as transaction fees.

        Must be called after :meth:`take_funds` (or :meth:`take_max_funds`)
        because the fee comes from the freshly-funded account workspace.
        Mirrors Rust ``IFaucet::pay_fee``.
        """
        label = self._account_workspace_label
        if label is None:
            signer = self.default_signer_address
            account = signer.to_component_address()
            self._want_list.add(
                WantInput.VaultForResource(
                    component=account, resource=ResourceAddress(TARI_TOKEN), required=True
                )
            )
            self._want_list.add(WantInput.SpecificSubstate(id=SubstateId(opaque=str(account))))
            self._builder.pay_fee_from_component(account, amount)
            return self
        self._builder.pay_fee_from_workspace_component(label, amount)
        return self

    def take_funds_stealth(
        self,
        statement: StealthTransferStatement,
        *,
        pay_fees_from_revealed: bool = True,
    ) -> Self:
        """Convert this faucet claim into a stealth deposit.

        Pre-condition: :meth:`take_funds` (or :meth:`take_max_funds`)
        must have been called so the account workspace exists. The
        revealed amount carried by ``statement.inputs_statement`` is
        withdrawn from that workspace and folded into a
        :class:`StealthTransferInstruction`. When
        ``pay_fees_from_revealed`` is ``True`` (default), the
        revealed-output bucket is routed back through
        :class:`PayFeeFromBucket` — matching Rust's
        ``and_pay_fee_from_revealed_output``. Stealth-specific glue
        lives in :mod:`ootle._async.stealth.faucet_path` — resolved
        via :func:`importlib.import_module` so the unasync-generated
        sync mirror picks up its sibling
        :mod:`ootle._sync.stealth.faucet_path` (landed in Step 06)
        without a hand-edited import substitution.
        """
        import importlib  # noqa: PLC0415

        package = __package__ or "ootle._async.builders"
        module = importlib.import_module(f"{package.rsplit('.', 1)[0]}.stealth.faucet_path")
        module.apply_take_funds_stealth(
            self._builder,
            self._want_list,
            self._account_workspace_label,
            statement,
            pay_fees_from_revealed=pay_fees_from_revealed,
            bucket_label=self._next_label("StealthBucket"),
            fee_bucket_label=self._next_label("StealthFee"),
        )
        return self

    def _next_label(self, prefix: str = "AccountInvokeBuilder") -> str:
        label = f"__{prefix}_{self._label_counter}"
        self._label_counter += 1
        return label
