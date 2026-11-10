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
    raw_body: object = json.loads(transaction.json)
    existing_sigs: list[object] = []
    body: object = raw_body
    if isinstance(raw_body, dict):
        doc = cast("dict[str, object]", raw_body)
        inner_sigs = doc.get("signatures")
        if "transaction" in doc and isinstance(inner_sigs, list):
            body = doc["transaction"]
            existing_sigs = list(cast("list[object]", inner_sigs))

    signatures: list[object] = []
    seen_pks: set[str] = set()
    for sig in existing_sigs:
        _append_unique_signature(signatures, seen_pks, sig)
    for auth in authorizations:
        for sig in _extract_signatures(auth.json):
            _append_unique_signature(signatures, seen_pks, sig)
    return json.dumps({"transaction": body, "signatures": signatures})


def _append_unique_signature(signatures: list[object], seen_pks: set[str], sig: object) -> None:
    item: object = sig
    if isinstance(sig, dict):
        doc = cast("dict[str, object]", sig)
        item = doc
        pk = doc.get("public_key")
        if isinstance(pk, str):
            if pk in seen_pks:
                return
            seen_pks.add(pk)
    if item not in signatures:
        signatures.append(item)


def _extract_signatures(auth_json: str) -> list[object]:
    doc: object = json.loads(auth_json)
    if isinstance(doc, dict):
        sigs = cast("dict[str, object]", doc).get("signatures")
        if isinstance(sigs, list):
            return cast("list[object]", sigs)
    return []
