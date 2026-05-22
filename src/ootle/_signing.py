"""Signing layer.

Defines the :class:`Signer` Protocol that :class:`OotleWallet` consumes,
the stealth-spend seams :class:`StealthSpendCrypto` and
:class:`StealthSigner`, and :class:`LocalSigner` — the in-process
implementation that wraps an :class:`OotleSecretKey` and satisfies both
:class:`Signer` and :class:`StealthSigner`.

All operations are synchronous — the WASM bridge is sync.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ootle._crypto import CryptoProvider
    from ootle._types.address import Address
    from ootle._types.keys import OotleSecretKey


class Signer(Protocol):
    """Per-key signing seam used by :class:`ootle.OotleWallet`.

    Implementations are structural — anything with these three methods
    can be ``register``-ed on a wallet.
    """

    def address(self) -> Address:
        """Return the :class:`Address` this signer signs for."""
        ...

    def add_signature(self, tx_json: str, seal_pk: bytes, *, crypto: CryptoProvider) -> str:
        """Append this signer's authorisation to ``tx_json``.

        ``seal_pk`` is the owner public key of the *seal* signer (the
        wallet's default). The signing message commits to it, so a
        co-signer must sign over the same value or the indexer rejects
        the envelope.

        Returns the updated transaction JSON.
        """
        ...

    def seal(self, tx_json: str, *, crypto: CryptoProvider) -> str:
        """Seal ``tx_json`` with this signer's secret. Returns sealed JSON."""
        ...


class StealthSpendCrypto(Protocol):
    """Crypto surface needed to sign a spent stealth-input UTXO.

    The two methods :meth:`LocalSigner.add_stealth_signature` composes:
    ``stealth_dh_secret`` (a :class:`~ootle._crypto.StealthCryptoProvider`
    method) to derive the one-time spend key, then ``add_transaction_signer``
    (a :class:`~ootle._crypto.CryptoProvider` method) to append its
    signature. The vendored ``WasmCryptoProvider`` satisfies both.
    """

    def stealth_dh_secret(
        self, network_byte: int, owner_secret: bytes, public_nonce: bytes
    ) -> bytes:
        """Derive the one-time stealth spend scalar ``c + k`` (32 bytes)."""
        ...

    def add_transaction_signer(self, tx_json: str, signer_sk: bytes, seal_pk: bytes) -> str:
        """Append a Schnorr signature from ``signer_sk`` to ``tx_json``."""
        ...


@runtime_checkable
class StealthSigner(Protocol):
    """A :class:`Signer` that can also sign a spent stealth-input UTXO.

    Implementations hold an account secret and derive the per-input
    one-time spend key on demand. ``LocalSigner`` satisfies it; the
    stealth authorizer narrows registered signers to this Protocol
    before asking them to authorise a stealth input.
    """

    def add_stealth_signature(
        self, tx_json: str, public_nonce: bytes, seal_pk: bytes, *, crypto: StealthSpendCrypto
    ) -> str:
        """Sign ``tx_json`` with the one-time key for ``public_nonce``."""
        ...


class LocalSigner:
    """A :class:`Signer` backed by an in-memory :class:`OotleSecretKey`.

    The :class:`Address` is computed on first call and cached.
    """

    __slots__ = ("_address_cache", "_secret")

    def __init__(self, secret: OotleSecretKey) -> None:
        self._secret = secret
        self._address_cache: Address | None = None

    def address(self) -> Address:
        """Return the :class:`Address` this signer signs for, cached."""
        if self._address_cache is None:
            self._address_cache = self._secret.to_address()
        return self._address_cache

    def add_signature(self, tx_json: str, seal_pk: bytes, *, crypto: CryptoProvider) -> str:
        """Append a Schnorr signature using the owner secret.

        ``seal_pk`` is the owner public key of the wallet's seal signer,
        which the signing message commits to.
        """
        return crypto.add_transaction_signer(tx_json, self._secret.owner_secret, seal_pk)

    def seal(self, tx_json: str, *, crypto: CryptoProvider) -> str:
        """Seal the transaction JSON with the owner secret."""
        return crypto.seal_transaction(tx_json, self._secret.owner_secret)

    def add_stealth_signature(
        self, tx_json: str, public_nonce: bytes, seal_pk: bytes, *, crypto: StealthSpendCrypto
    ) -> str:
        """Append a Schnorr signature from the one-time stealth spend key.

        Derives the one-time spend scalar ``c + k`` for the stealth UTXO
        whose sender nonce is ``public_nonce`` (Diffie-Hellman of this
        signer's account secret with that nonce), then signs ``tx_json``
        with it. Mirrors Rust ``sign_authorization_with_stealth``; the
        derived key's public key is the UTXO's ``SpendCondition::Signed``
        value, so the engine accepts the spend.

        ``seal_pk`` is the seal signer's owner public key the signing
        message commits to.
        """
        one_time_secret = crypto.stealth_dh_secret(
            self._secret.network.value, self._secret.owner_secret, public_nonce
        )
        return crypto.add_transaction_signer(tx_json, one_time_secret, seal_pk)
