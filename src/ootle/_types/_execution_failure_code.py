"""``ExecutionFailureCode`` — why an execution failure happened.

Mirrors the Rust ``ExecutionFailureCode`` enum in
``engine_types::commit_result``, carried by ``RejectReason::ExecutionFailure``.
"""

from __future__ import annotations

from typing import Literal

ExecutionFailureCode = Literal[
    "TemplateError",
    "AccessDenied",
    "AssertionFailed",
    "InsufficientFunds",
    "OutOfCompute",
    "LimitExceeded",
    "InvalidArgument",
    "NotFound",
    "DanglingResources",
    "ResourceRestricted",
    "InvalidProof",
    "EngineInvariant",
    "NotYetValid",
    "Unclassified",
]
"""Categorical code of an ``ExecutionFailure`` rejection."""
