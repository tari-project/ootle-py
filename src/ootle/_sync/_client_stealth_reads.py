"""Stealth-UTXO read helper consumed by :class:`OotleClient`.

:class:`ClientStealthReadsMixin` carries the client method; the free function
holds the logic so ``client.py`` stays under the 200-line ceiling.
``decrypt_owned_utxo`` is the recipient/owner AEAD read: it derives the value +
spend mask from the output's ``encrypted_data`` via ``decrypt_input_data``
(``unblind_output``), which needs no viewable-balance proof.

Substate-envelope parsing lives in :mod:`ootle._async._client_stealth_parse`.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, cast

from ootle._sync._client_stealth_parse import parse_substate_utxo
from ootle._sync._offload import offload
from ootle._crypto import ensure_stealth_capable
from ootle._wallet_stealth import decrypt_input_data

if TYPE_CHECKING:
    from ootle._crypto import CryptoProvider
    from ootle._crypto._stealth_provider import SyncStealthCryptoProvider
    from ootle._types.stealth import DecryptedData
    from ootle._types.substate import Substate


def decrypt_owned_utxo(
    crypto: object,
    view_secret: bytes,
    utxo: Substate,
) -> DecryptedData | None:
    """Decrypt a stealth UTXO this wallet owns via the AEAD owner-read.

    Derives the AEAD key from ``view_secret`` and the output's
    ``public_nonce`` to recover the value + spend mask — the read a
    *recipient* performs for an inbound stealth output. Returns ``None``
    when ``utxo`` is not a parseable stealth UTXO.
    """
    parsed = parse_substate_utxo(utxo)
    if parsed is None:
        return None
    commitment, body = parsed
    stealth = _require_stealth_crypto(crypto)
    return offload(
        partial(
            decrypt_input_data,
            stealth,
            commitment,
            body.encrypted_data,
            sender_public_nonce=body.public_nonce,
            view_secret=view_secret,
            skip_memo=True,
        )
    )


def _require_stealth_crypto(crypto: object) -> SyncStealthCryptoProvider:
    """Resolve the stealth provider for UTXO reads, defaulting to the WASM bridge."""
    return cast("SyncStealthCryptoProvider", ensure_stealth_capable(crypto))


class ClientStealthReadsMixin:
    """Mixin: the stealth-UTXO read method for :class:`OotleClient`.

    Extracted to keep ``client.py`` under the 200-line ceiling, mirroring
    :class:`ClientWritesMixin`. Declares the subclass-provided ``_crypto``
    attribute so Pyright stays strict-clean; the subclass initialises it.
    """

    _crypto: CryptoProvider | None

    def decrypt_owned_utxo(self, view_secret: bytes, utxo: Substate) -> DecryptedData | None:
        """Decrypt a stealth UTXO this wallet owns (AEAD owner-read).

        Recovers the value + spend mask of an inbound stealth output from its
        encrypted data, using the recipient view secret and the output's sender
        public nonce — the read a recipient performs. Returns ``None`` if
        ``utxo`` is not a parseable stealth UTXO.
        """
        return decrypt_owned_utxo(self._crypto, view_secret, utxo)
