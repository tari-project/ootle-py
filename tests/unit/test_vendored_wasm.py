"""Sanity tests for the committed WASM blob and its ``VERSION`` metadata."""

from __future__ import annotations

import hashlib
from importlib.resources import files

WASM_PKG = "ootle._crypto.wasm"
WASM_MAGIC = b"\x00asm"


def _read_version_lines() -> list[str]:
    text = (files(WASM_PKG) / "VERSION").read_text(encoding="utf-8")
    return text.splitlines()


def test_version_file_has_four_expected_lines() -> None:
    lines = _read_version_lines()
    assert len(lines) == 4
    assert lines[0].startswith("upstream:")
    assert lines[1].startswith("sha256:")
    assert lines[2].startswith("fetched:")
    assert lines[3].startswith("source:")


def test_blob_is_nonempty_and_starts_with_wasm_magic() -> None:
    blob = (files(WASM_PKG) / "ootle_wasm_bg.wasm").read_bytes()
    assert len(blob) > 0
    assert blob.startswith(WASM_MAGIC)


def test_blob_sha256_matches_version() -> None:
    blob = (files(WASM_PKG) / "ootle_wasm_bg.wasm").read_bytes()
    actual = hashlib.sha256(blob).hexdigest()
    expected = _read_version_lines()[1].split(":", 1)[1].strip()
    assert actual == expected
