"""Tests for the ``ootle.*`` logger namespace conventions."""

from __future__ import annotations

import logging

import pytest
from pytest_httpx import HTTPXMock

from ootle._async._transport import AsyncIndexerTransport
from ootle._crypto import _wasm_runtime as rt
from ootle.errors import CryptoBridgeError


def test_root_logger_has_null_handler() -> None:
    """`ootle/__init__` installs a NullHandler so unconfigured callers stay quiet."""
    handlers = logging.getLogger("ootle").handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)


async def test_transport_logs_connection_info(caplog: pytest.LogCaptureFixture) -> None:
    """``AsyncIndexerTransport.__init__`` logs an info-level URL line."""
    with caplog.at_level(logging.INFO, logger="ootle"):
        async with AsyncIndexerTransport("http://idx") as transport:
            assert transport.url == "http://idx"
    info_records = [
        r
        for r in caplog.records
        if r.name == "ootle._async._transport" and r.levelno == logging.INFO
    ]
    assert info_records, "expected an info-level transport connect log"
    assert "http://idx" in info_records[0].getMessage()


async def test_transport_logs_request_path_at_debug(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
) -> None:
    httpx_mock.add_response(url="http://idx/foo", json={"ok": True})
    with caplog.at_level(logging.DEBUG, logger="ootle._async._transport"):
        async with AsyncIndexerTransport("http://idx") as transport:
            await transport._request("GET", "foo")  # pyright: ignore[reportPrivateUsage]  # internal access
    debug_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("GET" in m and "/foo" in m for m in debug_msgs)


def test_wasm_sha_mismatch_logs_error_before_raising(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(rt, "_read_blob", lambda: b"\x00asm\x00\x00\x00\x00bogus")
    with caplog.at_level(logging.ERROR, logger="ootle._crypto._wasm_runtime"):
        with pytest.raises(CryptoBridgeError):
            rt.load_blob()
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "expected an error log on SHA mismatch"
    assert "SHA-256 mismatch" in error_records[0].getMessage()


async def test_no_secret_bytes_in_transport_logs(
    httpx_mock: HTTPXMock, caplog: pytest.LogCaptureFixture
) -> None:
    """The transport never logs request bodies, so secret material is never captured."""
    secret = "00112233445566778899aabbccddeeff" * 2
    httpx_mock.add_response(url="http://idx/foo", json={})
    with caplog.at_level(logging.DEBUG, logger="ootle"):
        async with AsyncIndexerTransport("http://idx") as transport:
            await transport._request("POST", "foo", json={"secret": secret})  # pyright: ignore[reportPrivateUsage]  # internal access
    for record in caplog.records:
        assert secret not in record.getMessage(), (
            "secret material leaked into log message: " + record.getMessage()
        )
