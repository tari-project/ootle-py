#!/usr/bin/env python3
"""Regenerate ``tests/fixtures/crypto_vectors.json`` and ``addresses_corpus.json``.

Recorded directly from the vendored ``ootle-wasm`` blob via
``WasmCryptoProvider`` — fixtures move in lockstep with the blob bumps.

Run after ``make update-wasm`` (or whenever the bridge's outputs need to
be re-snapshot)::

    uv run python scripts/regen_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ootle._crypto import load_default_provider
from ootle._crypto._wasm_runtime import _read_version

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "crypto_vectors.json"
ADDR_OUT = ROOT / "tests" / "fixtures" / "addresses_corpus.json"


def _wasm_meta() -> dict[str, str]:
    v = _read_version()
    return {"upstream": v.upstream, "sha256": v.sha256}


def _hex(b: bytes) -> str:
    return b.hex()


def _det(label: str, *parts: bytes) -> bytes:
    """Deterministic 32-byte canonical Ristretto scalar from fixed inputs."""
    h = hashlib.sha256()
    h.update(label.encode())
    for p in parts:
        h.update(p)
    raw = bytearray(h.digest())
    raw[31] &= 0x0F  # keep value below the curve25519 group order ≈ 2^252
    return bytes(raw)


def main() -> None:
    p = load_default_provider()

    pk_vectors = []
    for i in range(5):
        sk = _det(f"sk-{i}")
        pk = p.public_key_from_secret(sk)
        pk_vectors.append({"sk": _hex(sk), "pk": _hex(pk)})

    opk_vectors = []
    for i in range(5):
        owner_sk = _det(f"owner-sk-{i}")
        view_sk = _det(f"view-sk-{i}")
        owner_pk, view_pk = p.ootle_public_key_from_secret(owner_sk, view_sk)
        opk_vectors.append(
            {
                "owner_sk": _hex(owner_sk),
                "view_sk": _hex(view_sk),
                "owner_pk": _hex(owner_pk),
                "view_pk": _hex(view_pk),
            }
        )

    addr_vectors = []
    for i, network in enumerate([0x00, 0x10, 0x26]):
        owner_sk = _det(f"addr-owner-{i}")
        view_sk = _det(f"addr-view-{i}")
        owner_pk, view_pk = p.ootle_public_key_from_secret(owner_sk, view_sk)
        for memo in (None, b"memo-" + bytes([i])):
            addr = p.generate_ootle_address(owner_pk, view_pk, network, memo)
            parsed = p.parse_ootle_address(addr)
            assert parsed.owner_key == owner_pk
            assert parsed.view_key == view_pk
            assert parsed.network == network
            assert (parsed.memo or None) == memo
            addr_vectors.append(
                {
                    "owner_pk": _hex(owner_pk),
                    "view_pk": _hex(view_pk),
                    "network": network,
                    "memo": _hex(memo) if memo else None,
                    "address": addr,
                }
            )

    schnorr_vectors = []
    for i in range(3):
        sk = _det(f"sign-sk-{i}")
        msg = _det(f"sign-msg-{i}")
        schnorr_vectors.append({"sk": _hex(sk), "message": _hex(msg)})

    crypto_vectors = {
        "schema_version": 1,
        "wasm": _wasm_meta(),
        "note": (
            "Fixtures are derived from the vendored ootle-wasm blob. "
            "Regenerate with `uv run python scripts/regen_fixtures.py` "
            "when bumping the blob."
        ),
        "vectors": {
            "public_key_from_secret": pk_vectors,
            "ootle_public_key_from_secret": opk_vectors,
            "address_round_trip": addr_vectors,
            "schnorr_sign_inputs": schnorr_vectors,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(crypto_vectors, indent=2) + "\n", encoding="utf-8")

    addr_corpus = {
        "schema_version": 1,
        "wasm": _wasm_meta(),
        "vectors": addr_vectors,
    }
    ADDR_OUT.write_text(json.dumps(addr_corpus, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {ADDR_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
