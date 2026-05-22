"""Smoke tests for the Ootle CLI."""

from __future__ import annotations

import pytest

from ootle.cli import greeting, main


def test_greeting_uses_name() -> None:
    assert greeting("Tari") == "Hello from ootle, Tari!"


def test_main_prints_default_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Hello from ootle, world!"


def test_main_accepts_name_argument(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["Ada"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Hello from ootle, Ada!"


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_main_reports_version(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([flag])
    captured = capsys.readouterr()
    assert excinfo.value.code == 0
    assert captured.out.startswith("ootle ")
