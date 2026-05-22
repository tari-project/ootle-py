"""Tests for the local-source mode of ``scripts/update_wasm.py``.

These drive the CLI as a subprocess (``scripts/`` is not importable in the
pyright-strict/pytest setup) against a tiny fixture blob in ``tmp_path``.
The registry (``--version``) path is intentionally left untested here so
no test ever hits the network.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "update_wasm.py"
WASM_FILENAME = "ootle_wasm_bg.wasm"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - args are test-controlled
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _make_pkg(pkg_dir: Path, blob: bytes, version: str | None) -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / WASM_FILENAME).write_bytes(blob)
    if version is not None:
        (pkg_dir / "package.json").write_text(
            json.dumps({"name": "ootle-wasm", "version": version}), encoding="utf-8"
        )


def test_from_pkg_vendors_blob_and_writes_local_version(tmp_path: Path) -> None:
    blob = b"\x00asm\x01\x00\x00\x00fake-wasm-bytes-from-pkg"
    pkg = tmp_path / "pkg"
    _make_pkg(pkg, blob, version="0.31.0")
    target = tmp_path / "out"
    custom_source = "local build @ abc1234 (crates/ootle_wasm)"

    result = _run("--from-pkg", str(pkg), "--target-dir", str(target), "--source", custom_source)

    assert result.returncode == 0, result.stderr
    assert (target / WASM_FILENAME).read_bytes() == blob  # byte-for-byte copy
    sha = hashlib.sha256(blob).hexdigest()
    today = dt.datetime.now(tz=dt.UTC).date().isoformat()
    assert (target / "VERSION").read_text(encoding="utf-8") == (
        f"upstream: 0.31.0-local\nsha256:   {sha}\nfetched:  {today}\nsource:   {custom_source}\n"
    )


def test_from_file_uses_explicit_label_and_default_source(tmp_path: Path) -> None:
    blob = b"\x00asm\x01\x00\x00\x00fake-wasm-bytes-from-file"
    blob_path = tmp_path / "custom.wasm"
    blob_path.write_bytes(blob)
    target = tmp_path / "out"

    result = _run(
        "--from-file", str(blob_path), "--label", "0.99.0-local", "--target-dir", str(target)
    )

    assert result.returncode == 0, result.stderr
    lines = (target / "VERSION").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "upstream: 0.99.0-local"
    assert lines[3] == f"source:   local build ({blob_path})"


def test_from_file_without_label_errors(tmp_path: Path) -> None:
    blob_path = tmp_path / "x.wasm"
    blob_path.write_bytes(b"\x00asm")
    target = tmp_path / "out"

    result = _run("--from-file", str(blob_path), "--target-dir", str(target))

    assert result.returncode != 0
    assert "--label is required" in result.stderr
    assert not target.exists()


def test_missing_blob_errors(tmp_path: Path) -> None:
    target = tmp_path / "out"

    result = _run("--from-pkg", str(tmp_path / "nope"), "--target-dir", str(target))

    assert result.returncode != 0
    assert "blob not found" in result.stderr


def test_version_and_from_pkg_are_mutually_exclusive(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    _make_pkg(pkg, b"\x00asm", version="0.31.0")

    result = _run("--version", "0.30.0", "--from-pkg", str(pkg))

    assert result.returncode != 0
    assert "not allowed with" in result.stderr
