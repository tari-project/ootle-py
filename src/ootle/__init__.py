"""Ootle — Python client library for the Tari L2 network.

This module is the public surface. Names with a leading underscore
(``_async``, ``_sync``, ``_crypto``, ``_types``, ``_signing``,
``_instructions``) are internal — they may be renamed without a major
version bump. Diagnostics emit under the ``ootle.*`` logger namespace;
a :class:`logging.NullHandler` is installed on ``ootle`` so unconfigured
callers see no output. Opt in via ``logging.getLogger("ootle")``.
"""

from __future__ import annotations

import logging as _logging

from ootle._async._watcher import AsyncPendingTransaction
from ootle._async.builders import IAsyncAccount, IAsyncComponent, IAsyncFaucet
from ootle._async.client import AsyncOotleClient
from ootle._async.stealth._spec import StealthTransferSpec
from ootle._async.stealth.authorizer import AsyncWalletStealthAuthorizer
from ootle._async.stealth.transfer import AsyncStealthTransfer
from ootle._instructions import Arg, ArgVariant, args, metadata, workspace
from ootle._signing import LocalSigner, Signer
from ootle._sync._watcher import PendingTransaction
from ootle._sync.builders import IAccount, IComponent, IFaucet
from ootle._sync.client import OotleClient
from ootle._sync.stealth.authorizer import WalletStealthAuthorizer
from ootle._sync.stealth.transfer import StealthTransfer
from ootle._transaction_builder import TransactionBuilder
from ootle._types._tari_constants import TARI_TOKEN
from ootle._types.address import (
    Address,
    ComponentAddress,
    ParsedAddress,
    ResourceAddress,
    TemplateAddress,
)
from ootle._types.amount import TARI, Amount
from ootle._types.diff_summary import DiffSummary, UpSubstate
from ootle._types.events import TransactionEventFilter
from ootle._types.keys import OotlePublicKey, OotleSecretKey
from ootle._types.network import Network, default_indexer_url
from ootle._types.outcome import TransactionOutcome
from ootle._types.receipt import TransactionReceipt
from ootle._types.reject_reason import (
    Abort,
    AbortReason,
    ExecutionFailure,
    FailedToLockInputs,
    FailedToLockOutputs,
    FeePaymentInMainIntent,
    ForeignPledgeInputConflict,
    ForeignShardGroupDecidedToAbort,
    InsufficientFeesPaid,
    RejectReason,
    SubstateNotFound,
    UnknownRejectReason,
    format_reject_reason,
)
from ootle._types.stealth import (
    DecryptedData,
    EncryptedData,
    OneTimePublicKey,
    Output,
    SignatureRequirements,
    StealthInputsStatement,
    StealthOutputsStatement,
    StealthTransferStatement,
)
from ootle._types.substate import Substate, SubstateId, SubstateRequirement
from ootle._types.template import TemplateBlob
from ootle._types.transaction import (
    DryRunResult,
    Transaction,
    TransactionAuthorization,
    TransactionId,
    TransactionRequest,
    UnsignedTransaction,
)
from ootle._types.want_input import WantInput
from ootle._version import __version__, __wasm_version__
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
from ootle.wallet import OotleWallet

_logging.getLogger("ootle").addHandler(_logging.NullHandler())

__all__ = [
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
]
