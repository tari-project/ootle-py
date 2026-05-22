"""Stealth-input spend signing for :class:`WalletStealthAuthorizer`.

Split out of ``authorizer.py`` to respect the 200-line ceiling. Mirrors
Rust ``WalletStealthAuthorizer::create_authorizations``
(:file:`crates/wallet/ootle-rs/src/wallet/stealth.rs`): every spent
stealth-input UTXO carries ``spend_condition: Signed(<one-time pk>)``, so
the transaction must include a signature from the matching one-time
secret. Each required signer derives that secret from the UTXO's sender
``public_nonce`` and its account secret (see
:meth:`ootle._signing.LocalSigner.add_stealth_signature`) and signs the
unsigned transaction, committing to the account seal key. The account key
seals the folded transaction afterwards.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from ootle._sync._offload import offload
from ootle._signing import StealthSigner
from ootle._types.transaction import TransactionAuthorization
from ootle.errors import InvalidArgumentError, KeyProviderNotFoundError

if TYPE_CHECKING:
    from ootle._sync.stealth._spec import StealthTransferSpec
    from ootle._signing import StealthSpendCrypto
    from ootle._types.address import Address
    from ootle.wallet import OotleWallet


def create_stealth_authorizations(
    wallet: OotleWallet,
    spec: StealthTransferSpec,
    crypto: StealthSpendCrypto,
) -> tuple[TransactionAuthorization, ...]:
    """Produce one stealth-key authorization per spent stealth input.

    For each required signer the wallet's registered signer derives its
    one-time spend key from the UTXO ``public_nonce`` and signs the
    (post-:meth:`prepare`) unsigned transaction, committing to the account
    seal key. Fold the returned authorizations into the
    :class:`~ootle._types.transaction.TransactionRequest` you seal; the
    account key seals via :meth:`OotleWallet.seal`. Returns an empty tuple
    for a revealed-only transfer (no stealth inputs).

    Raises:
        NotImplementedError: A one-time stealth key must seal the
            transaction (the pure-stealth seal path is not yet supported).
        KeyProviderNotFoundError: No signer is registered for a required
            stealth signer's address.
        InvalidArgumentError: A registered signer cannot sign stealth
            inputs.
    """
    reqs = spec.signature_requirements
    if reqs.seal_signer() is not None:
        msg = "sealing a stealth transfer with a one-time stealth key is not supported yet"
        raise NotImplementedError(msg)
    seal_pk = wallet.default_address.owner_pk
    unsigned_json = spec.unsigned.json
    auths: list[TransactionAuthorization] = []
    for req in reqs.other_signers():
        signer = _stealth_signer_for(wallet, req.signer)
        signed = offload(
            partial(
                signer.add_stealth_signature,
                unsigned_json,
                req.public_nonce,
                seal_pk,
                crypto=crypto,
            )
        )
        auths.append(TransactionAuthorization(json=signed))
    return tuple(auths)


def _stealth_signer_for(wallet: OotleWallet, address: Address) -> StealthSigner:
    """Resolve the registered signer for ``address`` and narrow it to a stealth signer."""
    signer = wallet.signers.get(address)
    if signer is None:
        msg = f"no signer registered for {address.bech32m}"
        raise KeyProviderNotFoundError(msg, address=address)
    if not isinstance(signer, StealthSigner):
        msg = f"signer for {address.bech32m} cannot sign stealth inputs"
        raise InvalidArgumentError(msg)
    return signer
