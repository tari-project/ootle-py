"""Version metadata: package version and vendored WASM version.

``__version__`` comes from installed-package metadata (set by hatchling
from ``pyproject.toml``); editable trees fall back to ``"0.0.0+local"``.
The lookup uses the *distribution* name (``ootle-py``), which differs from
the *import* name (``ootle``) — using the import name raises
``PackageNotFoundError`` and silently degrades to the fallback.
``__wasm_version__`` is the first line of the vendored ``VERSION`` file
read via :func:`importlib.resources.files` so it works inside a wheel.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files

_DIST_NAME = "ootle-py"
_WASM_PKG = "ootle._crypto.wasm"
_VERSION_FILE = "VERSION"


def _resolve_package_version() -> str:
    try:
        return version(_DIST_NAME)
    except PackageNotFoundError:
        return "0.0.0+local"


def _resolve_wasm_version() -> str:
    text = (files(_WASM_PKG) / _VERSION_FILE).read_text(encoding="utf-8")
    return text.splitlines()[0].strip()


__version__: str = _resolve_package_version()
__wasm_version__: str = _resolve_wasm_version()
