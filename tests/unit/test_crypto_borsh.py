"""``bor_encode_transaction`` bridge tests.

Building a fully-shaped UnsignedTransactionV1 JSON is an M1 concern
(the wire types ship in M1.T3). At M0 we only verify the bridge
surface: invalid JSON propagates as ``CryptoBridgeError`` with the
right context, and the call shape (string in → string out) round-trips
through allocator/free without leaking.
"""

from __future__ import annotations

import pytest

from ootle._crypto import CryptoProvider
from ootle.errors import CryptoBridgeError


def test_bor_encode_rejects_invalid_json(crypto: CryptoProvider) -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        crypto.bor_encode_transaction("{not-valid-json")
    assert exc.value.context == "bor_encode_transaction"


def test_bor_encode_rejects_well_formed_but_wrong_shape(crypto: CryptoProvider) -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        crypto.bor_encode_transaction('{"V1": {}}')
    assert exc.value.context == "bor_encode_transaction"
