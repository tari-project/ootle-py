"""``SignatureRequirements`` and ``StealthSignerRequirement``.

Mirrors :file:`crates/wallet/ootle-rs/src/stealth/spec.rs` — the source
of the parity tests in
:mod:`tests/unit/stealth/test_stealth_spec.py`.

The Rust upstream uses ``IndexSet`` for ``required_signers`` — an
ordered set with insertion semantics. We mirror that with an internal
deduplicating builder so:

- order is preserved (insertion-stable);
- a given :class:`StealthSignerRequirement` appears at most once.

Both invariants are required by the upstream tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Self

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from ootle._types.address import Address

_RISTRETTO_PUBLIC_KEY_LEN: Final[int] = 32


@dataclass(frozen=True, slots=True)
class StealthSignerRequirement:
    """A signer that must contribute a signature to a stealth transfer.

    Mirrors ``StealthSignerRequirement``: an :class:`Address` and a
    32-byte Ristretto public-nonce that the signer pre-commits to.
    """

    signer: Address
    public_nonce: bytes

    def __post_init__(self) -> None:
        if len(self.public_nonce) != _RISTRETTO_PUBLIC_KEY_LEN:
            msg = (
                f"public_nonce must be {_RISTRETTO_PUBLIC_KEY_LEN} bytes, "
                f"got {len(self.public_nonce)}"
            )
            raise ValueError(msg)


def _dedup(signers: Iterable[StealthSignerRequirement]) -> tuple[StealthSignerRequirement, ...]:
    """Stable de-duplication, mirroring ``IndexSet::insert`` semantics."""
    seen: set[StealthSignerRequirement] = set()
    out: list[StealthSignerRequirement] = []
    for s in signers:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class SignatureRequirements:
    """Stealth-transfer signature contract.

    Captures the invariants around which signers a transaction needs in
    order to gain access to its inputs and/or substate components. The
    three modes (must-sign-with-account-key, opt-with-seal-signer,
    can-sign-with-ephemeral) are surfaced via the three predicate
    methods below — see the parity tests for the spec.
    """

    required_signers: tuple[StealthSignerRequirement, ...]
    _must_sign_with_account_key: bool
    seal_signer_override: StealthSignerRequirement | None

    @classmethod
    def new_must_sign_with_account_key(
        cls, required_signers: Iterable[StealthSignerRequirement]
    ) -> Self:
        """Build a spec where the account key must sign.

        Mirrors ``SignatureRequirements::new_must_sign_with_account_key``.
        The seal signer is always ``None`` in this mode — users sign
        with their account key.
        """
        return cls(
            required_signers=_dedup(required_signers),
            _must_sign_with_account_key=True,
            seal_signer_override=None,
        )

    @classmethod
    def new_opt_with_seal_signer(
        cls,
        required_signers: Iterable[StealthSignerRequirement],
        seal_signer: StealthSignerRequirement | None,
    ) -> Self:
        """Build a spec with an optional explicit seal signer.

        Mirrors ``SignatureRequirements::new_opt_with_seal_signer``. If
        ``required_signers`` is empty and ``seal_signer`` is ``None``,
        an ephemeral key can be used to seal the transaction.
        """
        return cls(
            required_signers=_dedup(required_signers),
            _must_sign_with_account_key=False,
            seal_signer_override=seal_signer,
        )

    def must_sign_with_account_key(self) -> bool:
        """Return ``True`` when the account key must sign the transfer."""
        return self._must_sign_with_account_key

    def can_sign_with_ephemeral_key(self) -> bool:
        """Return ``True`` when no specific signer is required.

        Mirrors
        ``!must_sign_with_account_key && required_signers.is_empty() && seal_signer.is_none()``.
        """
        return (
            not self._must_sign_with_account_key
            and not self.required_signers
            and self.seal_signer_override is None
        )

    def seal_signer(self) -> StealthSignerRequirement | None:
        """Return the seal signer for the transaction.

        - If :func:`must_sign_with_account_key` is ``True``, returns ``None``.
        - If :func:`can_sign_with_ephemeral_key` is ``True``, returns ``None``.
        - Otherwise: the explicit ``seal_signer`` if set, else the first
          required signer.
        """
        if self._must_sign_with_account_key:
            return None
        if self.seal_signer_override is not None:
            return self.seal_signer_override
        if not self.required_signers:
            return None
        return self.required_signers[0]

    def other_signers(self) -> Iterator[StealthSignerRequirement]:
        """Yield required signers that are *not* the implicit seal signer.

        Skips the first required signer iff
        ``!must_sign_with_account_key`` and there is no explicit
        ``seal_signer`` override — that signer is implicitly the seal.
        """
        skip = int(not self._must_sign_with_account_key and self.seal_signer_override is None)
        for i, s in enumerate(self.required_signers):
            if i < skip:
                continue
            yield s

    def __len__(self) -> int:
        return len(self.required_signers)

    def is_empty(self) -> bool:
        """Return ``True`` when no signers are required."""
        return not self.required_signers

    def required_signers_list(self) -> Sequence[StealthSignerRequirement]:
        """Return the required signers as an ordered sequence."""
        return self.required_signers
