"""View-secret validation for :class:`WalletStealthAuthorizer`.

The recipient's view secret decrypts the input masks of any stealth
inputs a spec carries. It is caller-owned — the :class:`Signer`
Protocol the wallet holds exposes no view key — so the authorizer
takes it as a parameter rather than deriving it from the wallet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ootle.errors import InvalidArgumentError

if TYPE_CHECKING:
    from ootle._sync.stealth._spec import StealthTransferSpec


_VIEW_SECRET_LEN = 32


def resolve_view_secret(spec: StealthTransferSpec, view_secret: bytes | None) -> bytes:
    """Validate the caller-supplied view secret against the spec's inputs.

    A spec with stealth inputs needs the recipient's view secret to
    decrypt each input mask; a revealed-only spec never touches it. A
    missing secret on the stealth path is an error rather than a silent
    fall-back to a zero key, which would produce garbage masks and an
    invalid balance proof.

    Args:
        spec: The transfer spec the authorizer will hydrate.
        view_secret: The caller-supplied 32-byte view secret, or ``None``.

    Returns:
        The validated view secret (the zero mask for a revealed-only spec
        with no secret supplied — it is never consulted in that case).

    Raises:
        InvalidArgumentError: A stealth-input spec was given no secret, or
            the supplied secret is not 32 bytes.
    """
    if spec.state.inputs_to_spend and view_secret is None:
        msg = "stealth inputs require a view_secret to decrypt their input masks"
        raise InvalidArgumentError(msg)
    if view_secret is None:
        return b"\x00" * _VIEW_SECRET_LEN
    if len(view_secret) != _VIEW_SECRET_LEN:
        msg = f"view_secret must be {_VIEW_SECRET_LEN} bytes, got {len(view_secret)}"
        raise InvalidArgumentError(msg)
    return view_secret
