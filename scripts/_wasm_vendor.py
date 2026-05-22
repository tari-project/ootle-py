"""Local-source helpers for :mod:`update_wasm`.

These cover the ``--from-pkg`` / ``--from-file`` vendoring modes: reading
a locally built blob and deriving the ``VERSION`` ``upstream:`` label and
``source:`` line. The registry (npm) path lives in :mod:`update_wasm`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

LOCAL_LABEL_SUFFIX = "-local"


def read_local_blob(path: Path) -> bytes:
    """Read the blob bytes at ``path``, erroring if it is missing."""
    if not path.is_file():
        raise SystemExit(f"blob not found: {path}")
    return path.read_bytes()


def pkg_json_version(pkg_dir: Path) -> str | None:
    """Read ``version`` from ``<pkg_dir>/package.json`` if present."""
    pkg_json = pkg_dir / "package.json"
    if not pkg_json.is_file():
        return None
    raw = json.loads(pkg_json.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    version = cast("dict[str, object]", raw).get("version")
    return version if isinstance(version, str) else None


def local_label(explicit: str | None, pkg_dir: Path | None) -> str:
    """Resolve the ``upstream:`` label for a local vendoring.

    Uses ``explicit`` verbatim when given; otherwise derives
    ``<package.json version>-local`` from ``pkg_dir``.
    """
    if explicit:
        return explicit
    version = pkg_json_version(pkg_dir) if pkg_dir is not None else None
    if version is None:
        raise SystemExit("--label is required (no package.json version to derive it from)")
    return f"{version}{LOCAL_LABEL_SUFFIX}"


def local_source(explicit: str | None, origin: Path) -> str:
    """Resolve the ``source:`` line, defaulting to ``local build (<origin>)``."""
    return explicit or f"local build ({origin})"
