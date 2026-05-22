"""Stealth statement carriers.

Mirrors the upstream wire shapes in
``crates/template_lib_types/src/stealth/statement.rs``:

- :class:`StealthInput` — a single 32-byte Pedersen commitment naming
  a UTXO to spend.
- :class:`StealthInputsStatement` — the set of stealth inputs plus the
  revealed-input amount.
- :class:`StealthOutputsStatement` — the output side of a transfer.
- :class:`StealthTransferStatement` — full transfer envelope (inputs +
  outputs + optional balance proof).

UTXO bodies (:class:`UnspentOutput`, :class:`StealthUnspentOutput`) and
the crypto-proof carriers (:class:`BalanceProofSignature`,
:class:`ViewableBalanceProof`) live in adjacent modules; they are
re-exported via :mod:`ootle._types.stealth` so callers don't notice
the split.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Self

from ootle._types.stealth._json import (
    bytes_to_hex,
    hex_field,
    hex_to_bytes,
    optional_dict,
    require_amount,
    require_dict,
    require_list,
)
from ootle._types.stealth._proofs import BalanceProofSignature
from ootle._types.stealth._unspent import StealthUnspentOutput

_PEDERSEN_COMMITMENT_LEN: Final[int] = 32


@dataclass(frozen=True, slots=True)
class StealthInput:
    """A reference to a stealth UTXO to be spent.

    Mirrors ``template_lib::types::stealth::StealthInput`` — a single
    32-byte Pedersen commitment.
    """

    commitment: bytes

    def __post_init__(self) -> None:
        if len(self.commitment) != _PEDERSEN_COMMITMENT_LEN:
            msg = (
                f"StealthInput.commitment must be {_PEDERSEN_COMMITMENT_LEN} bytes, "
                f"got {len(self.commitment)}"
            )
            raise ValueError(msg)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(commitment=hex_field(data, "commitment", length=_PEDERSEN_COMMITMENT_LEN))

    def to_json(self) -> dict[str, Any]:
        return {"commitment": bytes_to_hex(self.commitment)}


@dataclass(frozen=True, slots=True)
class StealthInputsStatement:
    """Input half of a stealth transfer.

    Rust's ``new`` constructor asserts ``revealed_amount`` is
    non-negative and at least one input *or* a non-zero revealed amount
    is provided. We enforce the same here.
    """

    inputs: tuple[StealthInput, ...]
    revealed_amount: int

    def __post_init__(self) -> None:
        if self.revealed_amount < 0:
            msg = f"revealed_amount must be non-negative, got {self.revealed_amount}"
            raise ValueError(msg)
        if not self.inputs and self.revealed_amount == 0:
            msg = "at least one input or a non-zero revealed amount must be provided"
            raise ValueError(msg)

    @classmethod
    def new_revealed_only(cls, amount: int) -> Self:
        """Match Rust ``StealthInputsStatement::new_revealed_only``."""
        return cls(inputs=(), revealed_amount=amount)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        inputs = tuple(StealthInput.from_json(d) for d in require_list(data, "inputs"))
        return cls(inputs=inputs, revealed_amount=require_amount(data, "revealed_amount"))

    def to_json(self) -> dict[str, Any]:
        return {
            "inputs": [i.to_json() for i in self.inputs],
            "revealed_amount": self.revealed_amount,
        }


@dataclass(frozen=True, slots=True)
class StealthOutputsStatement:
    """Output half of a stealth transfer.

    ``agg_range_proof`` is the bulletproof carrier — empty in
    revealed-only transfers.
    """

    outputs: tuple[StealthUnspentOutput, ...]
    revealed_output_amount: int
    agg_range_proof: bytes

    @classmethod
    def new_revealed_only(cls, amount: int) -> Self:
        """Match Rust ``StealthOutputsStatement::new_revealed_only``."""
        return cls(outputs=(), revealed_output_amount=amount, agg_range_proof=b"")

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        outputs = tuple(StealthUnspentOutput.from_json(d) for d in require_list(data, "outputs"))
        proof_raw = data.get("agg_range_proof")
        if proof_raw is None:
            proof = b""
        elif isinstance(proof_raw, str):
            proof = hex_to_bytes(proof_raw)
        else:
            msg = "agg_range_proof must be a hex string when present"
            raise TypeError(msg)
        return cls(
            outputs=outputs,
            revealed_output_amount=require_amount(data, "revealed_output_amount"),
            agg_range_proof=proof,
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "outputs": [o.to_json() for o in self.outputs],
            "revealed_output_amount": self.revealed_output_amount,
            "agg_range_proof": bytes_to_hex(self.agg_range_proof),
        }


@dataclass(frozen=True, slots=True)
class StealthTransferStatement:
    """Full stealth-transfer envelope.

    ``balance_proof`` is ``None`` iff the transfer is revealed-only.
    """

    inputs_statement: StealthInputsStatement
    outputs_statement: StealthOutputsStatement
    balance_proof: BalanceProofSignature | None = None

    @classmethod
    def revealed_only(cls, input_amount: int, output_amount: int) -> Self:
        """Match Rust ``StealthTransferStatement::revealed_only``."""
        return cls(
            inputs_statement=StealthInputsStatement.new_revealed_only(input_amount),
            outputs_statement=StealthOutputsStatement.new_revealed_only(output_amount),
            balance_proof=None,
        )

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        bp = optional_dict(data, "balance_proof")
        return cls(
            inputs_statement=StealthInputsStatement.from_json(
                require_dict(data, "inputs_statement")
            ),
            outputs_statement=StealthOutputsStatement.from_json(
                require_dict(data, "outputs_statement")
            ),
            balance_proof=None if bp is None else BalanceProofSignature.from_json(bp),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "inputs_statement": self.inputs_statement.to_json(),
            "outputs_statement": self.outputs_statement.to_json(),
            "balance_proof": None if self.balance_proof is None else self.balance_proof.to_json(),
        }
