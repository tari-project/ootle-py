"""Test-only :class:`Signer` implementations.

``StubSigner`` carries a pre-built :class:`Address` plus a marker byte
used to derive deterministic add-signature / seal outputs. It avoids
ever calling the WASM bridge during wallet unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ootle._crypto import CryptoProvider
    from ootle._types.address import Address


@dataclass(frozen=True, slots=True)
class StubSigner:
    """Signer fixture: returns deterministic strings keyed by ``label``."""

    addr: Address
    label: str

    def address(self) -> Address:
        return self.addr

    def add_signature(self, tx_json: str, seal_pk: bytes, *, crypto: CryptoProvider) -> str:
        # ``crypto`` is unused in tests but the Protocol mandates the kwarg.
        _ = crypto
        return f"{tx_json}|sig({self.label},seal={seal_pk[0]:02x})"

    def seal(self, tx_json: str, *, crypto: CryptoProvider) -> str:
        _ = crypto
        return f"sealed({self.label}):{tx_json}"
