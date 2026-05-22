"""``Address`` and ``ParsedAddress`` value types.

The bech32m string is the canonical form. ``Address.parse`` and
``Address.from_keys`` both delegate to the WASM crypto bridge — the
provider is loaded lazily inside the function bodies to keep the import
graph acyclic with :mod:`ootle._crypto`.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType, Self

from ootle._types.network import Network

if TYPE_CHECKING:
    from ootle._crypto import CryptoProvider


ComponentAddress = NewType("ComponentAddress", str)
"""Opaque component address as the wire emits it (``component_<hex64>``)."""

ResourceAddress = NewType("ResourceAddress", str)
"""Opaque resource address."""

TemplateAddress = NewType("TemplateAddress", str)
"""Opaque template address."""


# Component-address derivation, mirroring ootle-rs ``ToAccountAddress`` /
# ``derive_component_address_from_public_key``: a domain-separated Blake2b-256
# over ``ACCOUNT_TEMPLATE_ADDRESS`` and the Borsh-encoded owner public key.
# This is pure stdlib hashing over public inputs — the WASM bridge is not
# involved (and exposes no such export), but the byte layout must match the
# engine's exactly or the indexer rejects the derived id.
#
# ``hasher32(EngineHashDomainLabel::ComponentAddress)`` prepends its
# domain-separation tag as ``u64-LE(len(tag))`` followed by the tag bytes;
# the tag is ``"<TariEngineHashDomain.v0>.<label>"``.
_COMPONENT_ADDR_DOMAIN_TAG = b"com.tari.ootle.engine.v0.ComponentAddress"
_COMPONENT_ADDR_DOMAIN_SEP = (
    struct.pack("<Q", len(_COMPONENT_ADDR_DOMAIN_TAG)) + _COMPONENT_ADDR_DOMAIN_TAG
)
# ``ACCOUNT_TEMPLATE_ADDRESS`` is ``[0u8; 32]``; ``Hash32``'s derived Borsh
# impl writes a fixed array as 32 raw bytes with no length prefix.
_ACCOUNT_TEMPLATE_ADDRESS = bytes(32)


@dataclass(frozen=True, slots=True)
class ParsedAddress:
    """The bridge-side decomposition of an Ootle address.

    Mirrors :class:`ootle._crypto.ParsedAddress` but lives in the public
    types layer so that callers can import it from ``ootle`` without
    crossing the ``_crypto`` boundary.
    """

    owner_pk: bytes
    view_pk: bytes
    network: Network
    memo: bytes | None = None


@dataclass(frozen=True, slots=True)
class Address:
    """An Ootle account address.

    Attributes:
        bech32m: The canonical ``otl_…`` string form.
        network: The network this address belongs to.
        owner_pk: 32-byte owner (account) Ristretto public key.
        view_pk: 32-byte view-only Ristretto public key.
        memo: Optional opaque memo bytes encoded in the address.
    """

    bech32m: str
    network: Network
    owner_pk: bytes
    view_pk: bytes
    memo: bytes | None = None

    @classmethod
    def parse(cls, s: str, *, crypto: CryptoProvider | None = None) -> Self:
        """Decode a bech32m address into its components."""
        provider = _resolve_crypto(crypto)
        parsed = provider.parse_ootle_address(s)
        return cls(
            bech32m=s,
            network=Network(parsed.network),
            owner_pk=parsed.owner_key,
            view_pk=parsed.view_key,
            memo=parsed.memo,
        )

    @classmethod
    def from_keys(
        cls,
        owner_pk: bytes,
        view_pk: bytes,
        network: Network,
        memo: bytes | None = None,
        *,
        crypto: CryptoProvider | None = None,
    ) -> Self:
        """Build an :class:`Address` from its key components."""
        provider = _resolve_crypto(crypto)
        bech32m = provider.generate_ootle_address(owner_pk, view_pk, network.value, memo)
        return cls(
            bech32m=bech32m,
            network=network,
            owner_pk=owner_pk,
            view_pk=view_pk,
            memo=memo,
        )

    def to_component_address(self) -> ComponentAddress:
        """Derive this account's on-chain component address.

        Mirrors ``ToAccountAddress::to_account_address`` in ootle-rs. The
        indexer's substate API and the engine's component instructions want
        this ``component_<hex64>`` form — *not* the bech32m string.
        """
        h = hashlib.blake2b(digest_size=32)
        h.update(_COMPONENT_ADDR_DOMAIN_SEP)
        h.update(_ACCOUNT_TEMPLATE_ADDRESS)
        # RistrettoPublicKeyBytes serialises through Borsh as a ``&[u8]``
        # slice: a u32-LE length prefix followed by the key bytes.
        h.update(struct.pack("<I", len(self.owner_pk)))
        h.update(self.owner_pk)
        return ComponentAddress(f"component_{h.hexdigest()}")


def _resolve_crypto(crypto: CryptoProvider | None) -> CryptoProvider:
    if crypto is not None:
        return crypto
    from ootle._crypto import load_default_provider  # noqa: PLC0415

    return load_default_provider()
