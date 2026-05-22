"""``WalletStealthAuthorizer`` — ``Signer``-shaped stealth adapter.

Mirrors TS ``WalletStealthAuthorizer`` and the Rust ``StealthTransfer::
prepare`` signing surface (``crates/wallet/ootle-rs/src/stealth/builder.rs``).

## Design choice — (a) post-builder patching

Step 04 emits an *incomplete* :class:`StealthTransferInstruction` (no
balance proof, empty ``required_signers``); the authorizer hydrates it
by fetching stealth-input UTXOs, computing the input mask, signing the
balance proof, and **patching** the instruction in-place before seal.
This keeps the contract narrow — Step 04 owns the *shape*, Step 05 the
*crypto*.

## Signing

:meth:`prepare` hydrates the spec. :meth:`create_authorizations` then
signs each spent stealth input with its one-time spend key (see
``_authorizer_sign``); fold those in and the default signer seals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast

from ootle._sync._offload import offload
from ootle._sync.stealth._authorizer_helpers import (
    build_signature_requirements,
    fetch_stealth_input_bodies,
    patch_stealth_statement,
)
from ootle._sync.stealth._authorizer_sign import create_stealth_authorizations
from ootle._sync.stealth._builder_helpers import collect_input_signers
from ootle._sync.stealth._spec import StealthTransferSpec
from ootle._sync.stealth._view_secret import resolve_view_secret
from ootle._crypto import ensure_stealth_capable
from ootle._stealth_balance_proof import sign_balance_proof
from ootle._types.stealth import Mask, StealthTransferStatement
from ootle._types.transaction import UnsignedTransaction

if TYPE_CHECKING:
    from ootle._sync.client import OotleClient
    from ootle._crypto import CryptoProvider
    from ootle._crypto._stealth_provider import SyncStealthCryptoProvider
    from ootle._signing import Signer, StealthSpendCrypto
    from ootle._types.address import Address
    from ootle._types.transaction import TransactionAuthorization
    from ootle.wallet import OotleWallet


_ZERO_MASK = b"\x00" * 32


class WalletStealthAuthorizer:
    """``Signer``-shaped authorizer for a stealth transfer.

    Construct with the originating :class:`OotleWallet` and the
    :class:`StealthTransferSpec` emitted by
    :meth:`StealthTransfer.prepare`. Call :meth:`prepare` once
    against the live client to hydrate the balance proof, then
    register the authorizer on the wallet (or pass it as the seal
    signer) so :meth:`add_signature` / :meth:`seal` fire at seal time.
    """

    __slots__ = ("_must_sign_with_account_key", "_spec", "_view_secret", "_wallet")

    def __init__(
        self,
        wallet: OotleWallet,
        spec: StealthTransferSpec,
        *,
        must_sign_with_account_key: bool = True,
        view_secret: bytes | None = None,
    ) -> None:
        self._wallet = wallet
        self._spec = spec
        self._must_sign_with_account_key = must_sign_with_account_key
        self._view_secret = resolve_view_secret(spec, view_secret)

    @classmethod
    def from_spec(
        cls,
        wallet: OotleWallet,
        spec: StealthTransferSpec,
        *,
        view_secret: bytes | None = None,
    ) -> Self:
        """Build an authorizer from the spec; stealth transfers must sign with the account key.

        ``view_secret`` is the recipient's 32-byte view-only secret that
        decrypts the input masks of any stealth inputs in ``spec``. It is
        **required** when the spec carries stealth inputs and unused for a
        revealed-only transfer — never silently treated as a zero key.
        """
        return cls(wallet, spec, must_sign_with_account_key=True, view_secret=view_secret)

    @property
    def spec(self) -> StealthTransferSpec:
        """The (possibly post-prepare) :class:`StealthTransferSpec`."""
        return self._spec

    def address(self) -> Address:
        """:class:`Signer` Protocol — defers to the wallet's default address."""
        return self._wallet.default_address

    def prepare(self, client: OotleClient) -> StealthTransferSpec:
        """Hydrate the spec with balance proof + signature requirements.

        Mirrors Rust ``StealthTransfer::prepare`` lines 62-214: fetch
        stealth-input substates → aggregate input mask → sign balance
        proof → validate → patch the unsigned-tx JSON. Returns (and
        caches) the new :class:`StealthTransferSpec`.
        """
        crypto = self._stealth_crypto(client)
        inputs = collect_input_signers(self._spec.state)
        resolution = fetch_stealth_input_bodies(
            client=client,
            resource=self._spec.state.resource,
            inputs=inputs,
            crypto=crypto,
            view_secret=self._view_secret,
        )
        statement = self._sign_balance_proof(crypto, resolution.agg_input_mask)
        offload(lambda: crypto.validate_transfer(statement))
        new_unsigned = UnsignedTransaction(
            json=patch_stealth_statement(self._spec.unsigned.json, statement)
        )
        sig_reqs = build_signature_requirements(
            must_sign_with_account_key=self._must_sign_with_account_key,
            required=resolution.required_signers,
        )
        self._spec = StealthTransferSpec(
            unsigned=new_unsigned,
            statement=statement,
            signature_requirements=sig_reqs,
            output_mask=self._spec.output_mask,
            state=self._spec.state,
        )
        return self._spec

    def _sign_balance_proof(
        self, crypto: SyncStealthCryptoProvider, agg_input_mask: Mask
    ) -> StealthTransferStatement:
        """Sign the inputs == outputs balance proof and fold it into the statement."""
        statement = self._spec.statement
        if not statement.inputs_statement.inputs and not statement.outputs_statement.outputs:
            return statement
        output_mask = self._spec.output_mask
        if output_mask is None:
            output_mask = Mask(_ZERO_MASK)
        proof = offload(
            lambda: sign_balance_proof(
                crypto,
                input_mask=agg_input_mask,
                output_mask=output_mask,
                inputs_statement=statement.inputs_statement,
                outputs_statement=statement.outputs_statement,
            )
        )
        return StealthTransferStatement(
            inputs_statement=statement.inputs_statement,
            outputs_statement=statement.outputs_statement,
            balance_proof=proof,
        )

    def create_authorizations(self, client: OotleClient) -> tuple[TransactionAuthorization, ...]:
        """Sign each spent stealth input with its one-time spend key.

        Mirrors Rust ``WalletStealthAuthorizer::create_authorizations``.
        Call after :meth:`prepare`; fold the returned authorizations into
        the request you seal. Empty when no stealth inputs are spent.
        """
        crypto = cast("StealthSpendCrypto", self._stealth_crypto(client))
        return create_stealth_authorizations(self._wallet, self._spec, crypto)

    def add_signature(self, tx_json: str, seal_pk: bytes, *, crypto: CryptoProvider) -> str:
        """Append the account-key Schnorr signature, unless explicitly skipped."""
        if not self._must_sign_with_account_key:
            return tx_json
        signer = self._default_signer()
        return signer.add_signature(tx_json, seal_pk, crypto=crypto)

    def seal(self, tx_json: str, *, crypto: CryptoProvider) -> str:
        """Seal with the wallet's default signer (TS authorizer does the same)."""
        signer = self._default_signer()
        return signer.seal(tx_json, crypto=crypto)

    def _default_signer(self) -> Signer:
        addr = self._wallet.default_address
        return self._wallet.signers[addr]

    def _stealth_crypto(self, client: OotleClient) -> SyncStealthCryptoProvider:
        """Resolve the client's stealth provider, defaulting to the WASM bridge."""
        return cast(
            "SyncStealthCryptoProvider",
            ensure_stealth_capable(client._crypto),  # pyright: ignore[reportPrivateUsage]  # internal access
        )
