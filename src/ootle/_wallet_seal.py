"""Seal-time helpers consumed by :class:`OotleWallet.seal`.

Splice each :class:`TransactionAuthorization`'s signatures into the
unsigned-transaction body. Kept in a sibling module so ``wallet.py``
stays under the project's 200-line ceiling.

Mirrors Rust's ``TransactionRequest::build``: each
:class:`TransactionAuthorization` carries a pre-computed
``TransactionSignature`` (wrapped in the WASM-side
``UnsealedTransactionV1`` JSON shape ``{transaction, signatures}``).
Folding means collecting those signatures and producing an
``UnsealedTransactionV1`` JSON keyed off the original transaction body
— never replacing the body itself.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ootle._types.transaction import TransactionAuthorization, UnsignedTransaction


def fold_authorizations(
    transaction: UnsignedTransaction,
    authorizations: Sequence[TransactionAuthorization],
) -> str:
    """Splice each authorisation's signatures into ``transaction``.

    Returns ``transaction.json`` unchanged when ``authorizations`` is
    empty so the no-auth path stays a passthrough.
    """
    if not authorizations:
        return transaction.json
    signatures: list[object] = []
    for auth in authorizations:
        signatures.extend(_extract_signatures(auth.json))
    body: object = json.loads(transaction.json)
    return json.dumps({"transaction": body, "signatures": signatures})


def _extract_signatures(auth_json: str) -> list[object]:
    doc: object = json.loads(auth_json)
    if isinstance(doc, dict):
        sigs = cast("dict[str, object]", doc).get("signatures")
        if isinstance(sigs, list):
            return cast("list[object]", sigs)
    return []
