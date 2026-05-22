"""Allow `python -m ootle` to invoke the CLI."""

from ootle.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
