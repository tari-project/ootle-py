"""Shared stealth test constants."""

from __future__ import annotations

from typing import Final

REVEALED_RECEIVER: Final[bytes] = bytes.fromhex(
    "e2f2ae0a6abc4e71a884a961c500515f58e30b6aa582dd8db6a65945e08d2d76"
)
"""The compressed Ristretto basepoint — a canonical key to take a revealed output."""
