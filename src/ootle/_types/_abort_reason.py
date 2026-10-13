"""``AbortReason`` — why consensus aborted a transaction.

Mirrors the Rust ``AbortReason`` enum in ``engine_types::commit_result``,
carried by ``RejectReason::Abort`` and
``RejectReason::ForeignShardGroupDecidedToAbort``.
"""

from __future__ import annotations

from typing import Literal

AbortReason = Literal[
    "ForeignPledgeInputConflict",
    "LockInputsFailed",
    "LockOutputsFailed",
    "LockInputsOutputsFailed",
    "ExecutionFailure",
    "OneOrMoreInputsNotFound",
    "InsufficientFeesPaid",
    "FeePaymentInMainIntent",
    "EpochExpired",
    "ValidityWindowTooLong",
    "InputPledgeTooLarge",
]
"""Categorical reason an abort happened — Rust ``AbortReason`` enum.

The TS bindings (v1.30.0) miss ``EpochExpired``; Python follows Rust,
which is the canonical spec.
"""
