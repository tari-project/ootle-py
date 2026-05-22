"""``IComponent`` — catch-all component transaction builder.

The untyped-path replacement for the Rust ``ootle_template!`` macro.
Use via ``client.component()``::

    unsigned = await (
        client.component()
        .call_method(coin_addr, "increase_supply", args=[Amount(42)])
        .pay_fee(1000)
        .prepare()
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from ootle._sync.builders._arg_coerce import convert_arg
from ootle._sync.builders._base import BuilderBase
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import ComponentAddress, ResourceAddress, TemplateAddress
from ootle._types.instructions import CallFunction
from ootle._types.substate import SubstateId
from ootle._types.want_input import WantInput

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ootle._sync.client import OotleClient
    from ootle._instructions import ArgVariant
    from ootle._transaction_builder import TransactionBuilder
    from ootle._types.amount import Amount


class IComponent(BuilderBase):
    """Catch-all component builder. Construct via ``client.component()``."""

    __slots__ = ()

    def __init__(self, client: OotleClient) -> None:
        super().__init__(client)

    def call_method(
        self,
        component_or_workspace: ComponentAddress | ArgVariant,
        method: str,
        *,
        args: Sequence[ArgVariant] = (),
    ) -> Self:
        """Append ``CallMethod`` targeting a component address or workspace bucket.

        Args:
            component_or_workspace: A :class:`ComponentAddress` or a
                workspace reference from :func:`~ootle.workspace`.
            method: The method name to invoke.
            args: Keyword-only positional arguments for the method.
        """
        from ootle._instructions import Arg  # noqa: PLC0415

        instruction_args = tuple(convert_arg(self._builder, a) for a in args)
        if isinstance(component_or_workspace, Arg.NamedArg):
            self._builder.call_method_on_workspace(
                component_or_workspace.label, method, instruction_args
            )
        else:
            addr = ComponentAddress(str(component_or_workspace))
            self._builder.call_method(addr, method, instruction_args)
            # The target component and its vaults must be on-chain inputs — mirrors
            # Rust's `ComponentInvokeBuilder::call_method` (auto-fill + AllComponentVaults).
            self._want_list.add(WantInput.SpecificSubstate(id=SubstateId(opaque=str(addr))))
            self._want_list.add(WantInput.AllComponentVaults(component=addr))
        return self

    def call_function(
        self,
        template: TemplateAddress,
        function: str,
        *,
        args: Sequence[ArgVariant] = (),
    ) -> Self:
        """Append ``CallFunction`` targeting a template function.

        Args:
            template: The template address.
            function: The function name to invoke.
            args: Keyword-only positional arguments.
        """
        instruction_args = tuple(convert_arg(self._builder, a) for a in args)
        self._builder._body.instructions.append(  # pyright: ignore[reportPrivateUsage]  # internal access
            CallFunction(template_address=template, function=function, args=instruction_args)
        )
        return self

    def pay_fee(self, amount: Amount | int) -> Self:
        """Charge ``amount`` from the signer's account as transaction fees."""
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

    def put_last_instruction_output_on_workspace(self, label: str) -> Self:
        """Save the last instruction's output to a named workspace bucket."""
        self._builder.put_last_instruction_output_on_workspace(label)
        return self

    def want_vault_for(
        self,
        component: ComponentAddress,
        resource: ResourceAddress,
        *,
        required: bool = True,
    ) -> Self:
        """Register a want-input for a specific vault on ``component``."""
        self._want_list.add(
            WantInput.VaultForResource(component=component, resource=resource, required=required)
        )
        return self

    def want_substate(self, id: SubstateId, *, required: bool = True) -> Self:
        """Register a want-input for a specific substate by id."""
        self._want_list.add(WantInput.SpecificSubstate(id=id, required=required))
        return self

    def want_all_vaults(self, component: ComponentAddress) -> Self:
        """Register a want-input for every vault attached to ``component``."""
        self._want_list.add(WantInput.AllComponentVaults(component=component))
        return self

    def chain(self, other: BuilderBase) -> Self:
        """Merge another builder's instructions and want-list into this one.

        Workspace ids in *other* are remapped to avoid collisions with
        any ids already allocated in this builder.
        """
        self._builder.merge(other._builder)  # pyright: ignore[reportPrivateUsage]  # internal access
        self._want_list.update(other._want_list)  # pyright: ignore[reportPrivateUsage]  # internal access
        return self

    def then(self, f: Callable[[TransactionBuilder], TransactionBuilder]) -> Self:
        """Apply *f* to the underlying raw ``TransactionBuilder`` and return self."""
        self._builder.then(f)
        return self
