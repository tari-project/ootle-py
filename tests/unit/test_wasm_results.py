"""Unit tests for the result-unwrap helpers in ``_wasm_results``.

These pin the multi-value tuple contract (the index of ``err_ref`` / ``is_err``
within each shape) without a real WASM call. The error path patches
``_abi.take_externref`` — it needs a real ``wasmtime.Table`` otherwise — and the
``read_optional_str`` path drives the real UTF-8 decode through a fake bridge that
serves bytes out of an in-memory buffer.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ootle._crypto._bridge import Bridge, _abi
from ootle._crypto._wasm_results import (
    open_box,
    take_optional_u64_result,
    take_unit_result,
)
from ootle.errors import CryptoBridgeError

_GETTER = "__wbg_get_decryptedoutputresult_memo"
_FREER = "__wbg_decryptedoutputresult_free"


def _dummy_bridge() -> Bridge:
    """A bridge stand-in for success/error paths that never dereference it."""
    return cast("Bridge", object())


@pytest.fixture
def patched_externref(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``take_externref`` echo the index it was handed into the message."""

    def fake(_bridge: Bridge, idx: int) -> str:
        return f"wasm-error[{idx}]"

    monkeypatch.setattr(_abi, "take_externref", fake)


class _FakeMemory:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, _store: object, start: int, end: int) -> bytes:
        return self._data[start:end]


class _FakeBridge:
    """Minimal bridge serving one box getter and a no-op ``__wbindgen_free``."""

    def __init__(self, *, getter_return: tuple[int, int], data: bytes = b"") -> None:
        self.store: object = object()
        self.memory = _FakeMemory(data)
        self._getter_return = getter_return
        self.exports: dict[str, Any] = {
            _GETTER: self._getter,
            _FREER: self._free,
            "__wbindgen_free": self._free,
        }

    def _getter(self, _store: object, _ptr: int) -> tuple[int, int]:
        return self._getter_return

    def _free(self, _store: object, _ptr: int, _length: int, _align: int = 1) -> None:
        return None


def test_take_optional_u64_result_none() -> None:
    assert take_optional_u64_result(_dummy_bridge(), (0, 0, 0, 0), context="x") is None


def test_take_optional_u64_result_value() -> None:
    assert take_optional_u64_result(_dummy_bridge(), (1, 4242, 0, 0), context="x") == 4242


@pytest.mark.usefixtures("patched_externref")
def test_take_optional_u64_result_error() -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        take_optional_u64_result(_dummy_bridge(), (0, 0, 7, 1), context="decrypt")
    assert exc.value.context == "decrypt"
    assert str(exc.value.args[0]) == "wasm-error[7]"


def test_take_unit_result_ok() -> None:
    assert take_unit_result(_dummy_bridge(), (0, 0), context="x") is None


@pytest.mark.usefixtures("patched_externref")
def test_take_unit_result_error() -> None:
    with pytest.raises(CryptoBridgeError) as exc:
        take_unit_result(_dummy_bridge(), (5, 1), context="transfer")
    assert exc.value.context == "transfer"
    assert str(exc.value.args[0]) == "wasm-error[5]"


def test_read_optional_str_none() -> None:
    fake = _FakeBridge(getter_return=(0, 0))
    with open_box(cast("Bridge", fake), box_ptr=0, freer=_FREER) as box:
        assert box.read_optional_str(_GETTER) is None


def test_read_optional_str_decodes_utf8() -> None:
    memo = "café memo 🦀"
    encoded = memo.encode("utf-8")
    fake = _FakeBridge(getter_return=(1, len(encoded)), data=b"\x00" + encoded)
    with open_box(cast("Bridge", fake), box_ptr=0, freer=_FREER) as box:
        assert box.read_optional_str(_GETTER) == memo
