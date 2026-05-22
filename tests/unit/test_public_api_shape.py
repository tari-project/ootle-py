"""Public-surface contract: every name in ``__all__`` is importable.

If a future PR moves a symbol or removes one accidentally, this test
catches it before the user does.
"""

from __future__ import annotations

import importlib
from importlib.resources import files
from pathlib import Path

import ootle

EXPECTED_NAMES = {
    "TARI",
    "TARI_TOKEN",
    "Abort",
    "AbortReason",
    "Address",
    "Amount",
    "Arg",
    "ArgVariant",
    "AsyncOotleClient",
    "AsyncPendingTransaction",
    "AsyncStealthTransfer",
    "AsyncWalletStealthAuthorizer",
    "ComponentAddress",
    "CryptoBridgeError",
    "DecryptedData",
    "DefaultSignerNotSetError",
    "DiffSummary",
    "DryRunResult",
    "EncryptedData",
    "ExecutionFailure",
    "FailedToLockInputs",
    "FailedToLockOutputs",
    "FeePaymentInMainIntent",
    "ForeignPledgeInputConflict",
    "ForeignShardGroupDecidedToAbort",
    "IAccount",
    "IAsyncAccount",
    "IAsyncComponent",
    "IAsyncFaucet",
    "IComponent",
    "IFaucet",
    "IndexerClientError",
    "InsufficientFeesPaid",
    "InvalidArgumentError",
    "KeyProviderNotFoundError",
    "LocalSigner",
    "Network",
    "OneTimePublicKey",
    "OotleClient",
    "OotleError",
    "OotlePublicKey",
    "OotleSecretKey",
    "OotleWallet",
    "Output",
    "ParsedAddress",
    "PendingTransaction",
    "RejectReason",
    "ResourceAddress",
    "SignatureRequirements",
    "Signer",
    "SignerError",
    "StealthInputsStatement",
    "StealthOutputsStatement",
    "StealthTransfer",
    "StealthTransferSpec",
    "StealthTransferStatement",
    "Substate",
    "SubstateId",
    "SubstateNotFound",
    "SubstateRequirement",
    "TemplateAddress",
    "TemplateBlob",
    "Transaction",
    "TransactionAuthorization",
    "TransactionBuilder",
    "TransactionEventFilter",
    "TransactionId",
    "TransactionOutcome",
    "TransactionReceipt",
    "TransactionRejectedError",
    "TransactionRequest",
    "TransactionTimeoutError",
    "UnknownRejectReason",
    "UnsignedTransaction",
    "UpSubstate",
    "WalletError",
    "WalletStealthAuthorizer",
    "WantInput",
    "__version__",
    "__wasm_version__",
    "args",
    "default_indexer_url",
    "format_reject_reason",
    "metadata",
    "workspace",
}


def test_all_matches_expected_set() -> None:
    assert set(ootle.__all__) == EXPECTED_NAMES


def test_every_name_in_all_is_present_on_module() -> None:
    for name in ootle.__all__:
        assert hasattr(ootle, name), f"missing public symbol: {name}"


def test_public_module_can_be_imported_via_importlib() -> None:
    mod = importlib.import_module("ootle")
    assert mod is ootle


def test_version_is_non_empty_string() -> None:
    assert isinstance(ootle.__version__, str)
    assert ootle.__version__


def test_wasm_version_matches_first_line_of_vendor_file() -> None:
    expected = (
        (files("ootle._crypto.wasm") / "VERSION")
        .read_text(encoding="utf-8")
        .splitlines()[0]
        .strip()
    )
    assert ootle.__wasm_version__ == expected
    assert ootle.__wasm_version__


def test_wasm_version_contains_upstream_tag_from_repo_file() -> None:
    """Sanity-check the on-disk ``VERSION`` file shape, independent of imports."""
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "src/ootle/_crypto/wasm/VERSION").read_text(encoding="utf-8")
    assert text.splitlines()[0].startswith("upstream:")
