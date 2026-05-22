"""``add_transaction_signer`` / ``seal_transaction`` / ``hash_unsigned_transaction`` bridge tests.

A fully-shaped UnsignedTransactionV1 JSON is an M1 concern. Here we
only check that the bridge surface error-handles bad input correctly
and that the panic/error path returns ``CryptoBridgeError`` with the
expected ``context`` label.
"""

from __future__ import annotations

import pytest

from ootle._crypto import CryptoProvider
from ootle.errors import CryptoBridgeError

DUMMY_SK = bytes(32)
DUMMY_PK = bytes(32)


def test_hash_unsigned_transaction_rejects_invalid_json(crypto: CryptoProvider) -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        crypto.hash_unsigned_transaction("not-json", DUMMY_PK)
    assert exc.value.context == "hash_unsigned_transaction"


def test_seal_transaction_rejects_invalid_json(crypto: CryptoProvider) -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        crypto.seal_transaction("not-json", DUMMY_SK)
    assert exc.value.context == "seal_transaction"


def test_add_transaction_signer_rejects_invalid_json(crypto: CryptoProvider) -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        crypto.add_transaction_signer("not-json", DUMMY_SK, DUMMY_PK)
    assert exc.value.context == "add_transaction_signer"
