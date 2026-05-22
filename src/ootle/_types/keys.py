"""Secret and public key wrappers.

``OotleSecretKey`` carries the network it was generated for and never
prints its raw bytes. ``OotleSecretKey.random`` and ``to_address`` both
delegate to the WASM crypto bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, override

from ootle._types.address import Address

if TYPE_CHECKING:
    from ootle._crypto import CryptoProvider
    from ootle._types.network import Network


@dataclass(frozen=True, slots=True)
class OotlePublicKey:
    """The two Ristretto public keys an Ootle account exposes."""

    owner_pk: bytes
    view_pk: bytes


@dataclass(frozen=True, slots=True, repr=False)
class OotleSecretKey:
    """An Ootle account's two secret keys.

    Attributes:
        network: The network these keys are bound to.
        owner_secret: 32-byte owner (account spending) Ristretto secret.
        view_secret: 32-byte view-only Ristretto secret (decrypts inbound
            stealth UTXOs in v2).
    """

    network: Network
    owner_secret: bytes
    view_secret: bytes

    @classmethod
    def random(cls, network: Network, *, crypto: CryptoProvider | None = None) -> Self:
        """Generate a fresh ``(owner_secret, view_secret)`` pair."""
        provider = _resolve_crypto(crypto)
        owner, view = provider.generate_ootle_secret_key()
        return cls(network=network, owner_secret=owner, view_secret=view)

    def public_keys(self, *, crypto: CryptoProvider | None = None) -> OotlePublicKey:
        """Derive the ``(owner_pk, view_pk)`` pair via the bridge."""
        provider = _resolve_crypto(crypto)
        owner, view = provider.ootle_public_key_from_secret(self.owner_secret, self.view_secret)
        return OotlePublicKey(owner_pk=owner, view_pk=view)

    def to_address(self, *, crypto: CryptoProvider | None = None) -> Address:
        """Derive the bech32m :class:`Address` for this secret key."""
        provider = _resolve_crypto(crypto)
        pks = self.public_keys(crypto=provider)
        return Address.from_keys(pks.owner_pk, pks.view_pk, self.network, crypto=provider)

    @override
    def __repr__(self) -> str:
        return (
            f"OotleSecretKey(network={self.network!r}, "
            f'owner_secret=b"<32 bytes>", '
            f'view_secret=b"<32 bytes>")'
        )


def _resolve_crypto(crypto: CryptoProvider | None) -> CryptoProvider:
    if crypto is not None:
        return crypto
    from ootle._crypto import load_default_provider  # noqa: PLC0415

    return load_default_provider()
