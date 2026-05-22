"""Parity tests for ``SignatureRequirements``.

One-to-one ports of the invariant suite at
``crates/wallet/ootle-rs/src/stealth/spec.rs`` lines 179-244 (the
``signature_requirement_invariants`` module). Each Rust test maps to a
``test_*`` function below; the docstring quotes the Rust intent.

Synthetic 32-byte public-nonces are used in place of real Ristretto
keys — the spec tests exercise pure ordering / membership logic, not
cryptographic relations, so the byte values just need to be distinct.
"""

from __future__ import annotations

from ootle._types.address import Address
from ootle._types.network import Network
from ootle._types.stealth.requirements import (
    SignatureRequirements,
    StealthSignerRequirement,
)


def _signer_from_seed(seed: int) -> StealthSignerRequirement:
    """Build a deterministic :class:`StealthSignerRequirement`.

    Mirrors the Rust fixture ``signer_from_seed`` at lines 172-177 of
    ``spec.rs``: ``[seed; 32]`` for owner/view bytes, ``[seed; 32]``
    for the public nonce, ``Network::LocalNet``.
    """
    pk = bytes([seed]) * 32
    addr = Address(
        bech32m=f"otl_loc_seed_{seed:02x}",
        network=Network.LOCAL_NET,
        owner_pk=pk,
        view_pk=pk,
    )
    return StealthSignerRequirement(signer=addr, public_nonce=pk)


def test_invariant1_must_sign_with_account_key() -> None:
    """spec.rs:182-198 — must_sign_with_account_key → seal_signer is None.

    All required signers are returned by ``other_signers()``.
    """
    signer1 = _signer_from_seed(1)
    signer2 = _signer_from_seed(2)

    spec = SignatureRequirements.new_must_sign_with_account_key([signer1, signer2])
    assert spec.must_sign_with_account_key() is True
    assert spec.can_sign_with_ephemeral_key() is False
    assert spec.seal_signer() is None

    assert list(spec.other_signers()) == [signer1, signer2]


def test_invariant2_opt_seal_signer_default_and_override() -> None:
    """spec.rs:200-232 — opt_with_seal_signer cases.

    When ``seal_signer`` override is ``None`` the first required signer
    becomes the implicit seal signer; with an override, the explicit
    one is the seal signer and *all* required signers fall under
    ``other_signers``.
    """
    signer1 = _signer_from_seed(1)
    signer2 = _signer_from_seed(2)

    # Case 1: no override → first required signer is the seal signer.
    spec = SignatureRequirements.new_opt_with_seal_signer([signer1, signer2], None)
    assert spec.must_sign_with_account_key() is False
    assert spec.can_sign_with_ephemeral_key() is False
    assert spec.seal_signer() == signer1
    assert list(spec.other_signers()) == [signer2]

    # Case 2: explicit seal signer override → both required signers
    # appear in other_signers; the override is the seal signer.
    signer3 = _signer_from_seed(3)
    spec = SignatureRequirements.new_opt_with_seal_signer([signer1, signer3], signer2)
    assert spec.must_sign_with_account_key() is False
    assert spec.can_sign_with_ephemeral_key() is False
    assert spec.seal_signer() == signer2
    assert list(spec.other_signers()) == [signer1, signer3]


def test_invariant3_can_sign_with_ephemeral_key() -> None:
    """spec.rs:234-244 — empty signers, no override → ephemeral key path.

    ``can_sign_with_ephemeral_key()`` is ``True``; both ``seal_signer``
    and the ``other_signers`` iterator are empty.
    """
    spec = SignatureRequirements.new_opt_with_seal_signer([], None)
    assert spec.must_sign_with_account_key() is False
    assert spec.can_sign_with_ephemeral_key() is True
    assert spec.seal_signer() is None
    assert next(iter(spec.other_signers()), None) is None
