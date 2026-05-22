"""Error taxonomy: hierarchy, structured attributes, and ``str``."""

from __future__ import annotations

from ootle._types.reject_reason import ExecutionFailure
from ootle._types.transaction import TransactionId
from ootle.errors import (
    CryptoBridgeError,
    DefaultSignerNotSetError,
    IndexerClientError,
    InvalidArgumentError,
    KeyProviderNotFoundError,
    OotleError,
    SignerError,
    TransactionRejectedError,
    TransactionTimeoutError,
    WalletError,
)


def test_every_error_is_an_ootle_error() -> None:
    for cls in (
        IndexerClientError,
        TransactionRejectedError,
        TransactionTimeoutError,
        WalletError,
        KeyProviderNotFoundError,
        DefaultSignerNotSetError,
        SignerError,
        CryptoBridgeError,
        InvalidArgumentError,
    ):
        assert issubclass(cls, OotleError)


def test_wallet_subclasses_are_walleterrors() -> None:
    assert issubclass(KeyProviderNotFoundError, WalletError)
    assert issubclass(DefaultSignerNotSetError, WalletError)


def test_wallet_namespace_attributes_resolve_to_subclasses() -> None:
    assert WalletError.KeyProviderNotFoundError is KeyProviderNotFoundError
    assert WalletError.DefaultSignerNotSetError is DefaultSignerNotSetError


def test_indexer_client_error_carries_attributes() -> None:
    err = IndexerClientError("boom", status=503, body="oops", url="http://x/y")
    assert err.status == 503
    assert err.body == "oops"
    assert err.url == "http://x/y"
    assert "status=503" in str(err)
    assert "url=http://x/y" in str(err)


def test_indexer_client_error_accepts_none_status() -> None:
    err = IndexerClientError("connect failed", status=None, body="", url="http://x/y")
    assert err.status is None


def test_transaction_rejected_error_carries_attributes() -> None:
    tx_id = TransactionId("tx-1")
    err = TransactionRejectedError("nope", tx_id=tx_id, reason="bad-fee")
    assert err.tx_id == tx_id
    assert err.reason == "bad-fee"
    assert err.reject_reason is None
    assert "tx_id=tx-1" in str(err)
    assert "reason=bad-fee" in str(err)


def test_transaction_rejected_error_carries_optional_reject_reason() -> None:
    rr = ExecutionFailure("boom")
    err = TransactionRejectedError(
        "nope",
        tx_id=TransactionId("tx-1"),
        reason="Execution failure: boom",
        reject_reason=rr,
    )
    assert err.reject_reason is rr


def test_transaction_timeout_error_carries_tx_id() -> None:
    tx_id = TransactionId("tx-2")
    err = TransactionTimeoutError("waited too long", tx_id=tx_id)
    assert err.tx_id == tx_id
    assert "tx_id=tx-2" in str(err)


def test_key_provider_not_found_error_carries_address() -> None:
    err = KeyProviderNotFoundError("missing", address="otl_loc_abc")
    assert err.address == "otl_loc_abc"


def test_crypto_bridge_error_preserves_context_and_chains_cause() -> None:
    inner = ValueError("inner")
    try:
        try:
            raise inner
        except ValueError as exc:
            raise CryptoBridgeError("trap", context="schnorr_sign") from exc
    except CryptoBridgeError as err:
        assert err.context == "schnorr_sign"
        assert err.__cause__ is inner
        assert str(err) == "[schnorr_sign] trap"


def test_crypto_bridge_error_without_context() -> None:
    err = CryptoBridgeError("trap")
    assert err.context is None
    assert err.__cause__ is None
    assert str(err) == "trap"


def test_signer_error_and_invalid_argument_error_are_simple() -> None:
    s = SignerError("no key")
    a = InvalidArgumentError("bad arg")
    assert isinstance(s, OotleError)
    assert isinstance(a, OotleError)
    assert str(s) == "no key"
    assert str(a) == "bad arg"


def test_default_signer_not_set_error_constructs_with_message_only() -> None:
    err = DefaultSignerNotSetError("no default")
    assert isinstance(err, WalletError)
    assert str(err) == "no default"
