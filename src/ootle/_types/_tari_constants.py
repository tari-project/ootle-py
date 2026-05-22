"""Tari well-known on-chain addresses (mirrors ``tari_template_lib_types::constants``)."""

from __future__ import annotations

from typing import Final

XTR_FAUCET_COMPONENT_ADDRESS: Final[str] = (
    "component_0102030000000000000000000000000000000000000000000000000000000000"
)
"""On-chain XTR faucet component (``ObjectKey`` ``[1, 2, 3, 0, …, 0]``)."""

XTR_FAUCET_VAULT_ADDRESS: Final[str] = (
    "vault_0102030000000000000000000000000000000000000000000000000000000001"
)
"""Vault held by the XTR faucet (``ObjectKey`` ``[1, 2, 3, 0, …, 0, 1]``)."""

# S105: this is a well-known public on-chain address, not a hard-coded credential.
TARI_TOKEN: Final[str] = "resource_0101010101010101010101010101010101010101010101010101010101010101"  # noqa: S105
"""Native TARI (XTR) token resource (``STEALTH_TARI_RESOURCE_ADDRESS``, ``[1u8; 32]``)."""

XTR_FAUCET_CLAIM_RESOURCE_ADDRESS: Final[str] = (
    "resource_0102030000000000000000000000000000000000000000000000000000000002"
)
"""Claim resource held by the XTR faucet (``ObjectKey`` ``[1, 2, 3, 0, …, 0, 2]``)."""
