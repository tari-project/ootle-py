"""Command-line interface for Ootle."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from ootle import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence


def greeting(name: str) -> str:
    """Build the greeting string used by the CLI."""
    return f"Hello from ootle, {name}!"


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser for the `ootle` CLI."""
    parser = argparse.ArgumentParser(prog="ootle")
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"ootle {__version__}",
    )
    parser.add_argument("name", nargs="?", default="world")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the `ootle` console script.

    Args:
        argv: Optional argument list. Defaults to ``sys.argv[1:]``.

    Returns:
        A POSIX exit code (``0`` on success).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    print(greeting(args.name))
    return 0
