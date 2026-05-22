"""``IAccount`` — account transaction builder.

Provides ``pay_fee``, ``public_transfer``, and ``publish_template``.
Use via ``client.account()``::

    unsigned = await (
        client.account().pay_fee(1000).public_transfer(recipient, TARI_TOKEN, 2 * TARI).prepare()
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._sync.builders._base import BuilderBase
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ResourceAddress
from ootle._types.instructions import amount_literal, resource_address_literal
from ootle._types.substate import SubstateId
from ootle._types.want_input import WantInput
from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._sync.client import OotleClient
    from ootle._types.address import Address
    from ootle._types.amount import Amount
    from ootle._types.template import TemplateBlob


class IAccount(BuilderBase):
    """Account transaction builder. Construct via ``client.account()``."""

    __slots__ = ()

    def __init__(self, client: OotleClient) -> None:
        super().__init__(client)

    def pay_fee(self, amount: Amount | int) -> Self:
        """Charge ``amount`` from the signer's account as transaction fees.

        Mirrors Rust ``IAccount::pay_fee``.
        """
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

    def public_transfer(
        self,
        to: Address,
        resource: ResourceAddress,
        amount: Amount | int,
    ) -> Self:
        """Withdraw ``amount`` of ``resource`` and deposit into ``to``'s account.

        Mirrors Rust ``IAccount::public_transfer``.

        Raises:
            InvalidArgumentError: ``amount`` is not positive.
        """
        if int(amount) <= 0:
            msg = f"transfer amount must be positive, got {int(amount)}"
            raise InvalidArgumentError(msg)
        signer = self.default_signer_address
        from_account = signer.to_component_address()
        to_account = to.to_component_address()
        bucket_label = f"__AccountInvokeBuilder_{self._builder.next_workspace_id()}"
        self._want_list.add(
            WantInput.VaultForResource(component=from_account, resource=resource, required=True)
        )
        # `withdraw` is a method call on `from_account` — it must be an on-chain input.
        self._want_list.add(WantInput.SpecificSubstate(id=SubstateId(opaque=str(from_account))))
        self._want_list.add(
            WantInput.SpecificSubstate(id=SubstateId(opaque=str(to_account)), required=False)
        )
        self._want_list.add(
            WantInput.VaultForResource(component=to_account, resource=resource, required=False)
        )
        (
            self._builder.call_method(
                from_account,
                "withdraw",
                (resource_address_literal(resource), amount_literal(amount)),
            )
            .put_last_instruction_output_on_workspace(bucket_label)
            .create_account(to.owner_pk, bucket_workspace_label=bucket_label)
        )
        return self

    def publish_template(self, template_blob: bytes | TemplateBlob) -> Self:
        """Publish a compiled WASM template.

        Accepts either raw ``bytes`` or a :class:`TemplateBlob` wrapper.
        Mirrors Rust ``IAccount::publish_template``.
        """
        from ootle._types.template import TemplateBlob as _TemplateBlob  # noqa: PLC0415

        blob = template_blob.blob if isinstance(template_blob, _TemplateBlob) else template_blob
        self._builder.publish_template(blob)
        return self
