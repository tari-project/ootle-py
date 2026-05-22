"""Shared JSON helpers for the stealth value types.

Carries:

- ``dumps_stable`` — pinned compact, sort-keys encoder. Every public
  ``to_json_bytes`` helper on a stealth type goes through this so the
  engine hashes the same bytes the Rust serde encoder would.
- ``hex_to_bytes`` / ``bytes_to_hex`` — Rust's ``serde_helpers::fixed_hex``
  emits lower-case hex with no ``0x`` prefix.
- ``require_*`` / ``optional_*`` extractors specialised to the stealth
  payload shapes (hex strings of fixed length, lists of objects).

Keep this module free of imports from sibling stealth modules — they
all depend on it.
"""

from __future__ import annotations

import json
from typing import Any, cast


def hex_to_bytes(s: str) -> bytes:
    """Decode a lower-case hex string to ``bytes``.

    Mirrors ``serde_helpers::fixed_hex``: no ``0x`` prefix, even length.
    """
    if s.startswith("0x"):
        msg = "hex string must not include a '0x' prefix"
        raise ValueError(msg)
    return bytes.fromhex(s)


def bytes_to_hex(b: bytes) -> str:
    """Encode bytes as lower-case hex with no prefix."""
    return b.hex()


def hex_field(payload: dict[str, Any], key: str, *, length: int | None = None) -> bytes:
    """Extract ``payload[key]`` as a hex string and decode to bytes."""
    raw = payload[key]
    if not isinstance(raw, str):
        msg = f"field {key!r} must be a hex string, got {type(raw).__name__}"
        raise TypeError(msg)
    decoded = hex_to_bytes(raw)
    if length is not None and len(decoded) != length:
        msg = f"field {key!r} must decode to {length} bytes, got {len(decoded)}"
        raise ValueError(msg)
    return decoded


def optional_hex_field(
    payload: dict[str, Any], key: str, *, length: int | None = None
) -> bytes | None:
    """Extract an optional hex string into bytes (``None`` if missing/null)."""
    if key not in payload or payload[key] is None:
        return None
    return hex_field(payload, key, length=length)


def require_int(payload: dict[str, Any], key: str) -> int:
    """Return ``payload[key]`` as a Python ``int`` (rejecting ``bool``)."""
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"field {key!r} must be an int, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def require_amount(payload: dict[str, Any], key: str) -> int:
    """Return an ``Amount``-typed field as ``int``, accepting int or str.

    Tari serialises ``Amount`` as a JSON *string* (JS BigInt safety) — the
    WASM blob does this — while the Python ``to_json`` emits a plain int.
    Accept both; reject ``bool`` and non-numeric strings.
    """
    value = payload[key]
    if isinstance(value, bool):
        msg = f"field {key!r} must be an integer amount, got bool"
        raise TypeError(msg)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            msg = f"field {key!r} must be an integer amount, got {value!r}"
            raise TypeError(msg) from exc
    msg = f"field {key!r} must be an int or stringified int, got {type(value).__name__}"
    raise TypeError(msg)


def optional_int(payload: dict[str, Any], key: str) -> int | None:
    """Return ``payload[key]`` as ``int`` if present, else ``None``."""
    if key not in payload or payload[key] is None:
        return None
    return require_int(payload, key)


def require_list(payload: dict[str, Any], key: str) -> list[Any]:
    """Return ``payload[key]`` as a list."""
    value = payload[key]
    if not isinstance(value, list):
        msg = f"field {key!r} must be an array, got {type(value).__name__}"
        raise TypeError(msg)
    return cast("list[Any]", value)


def require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``payload[key]`` as a dict."""
    value = payload[key]
    if not isinstance(value, dict):
        msg = f"field {key!r} must be an object, got {type(value).__name__}"
        raise TypeError(msg)
    return cast("dict[str, Any]", value)


def optional_dict(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    """Return ``payload[key]`` as a dict when present and non-null."""
    if key not in payload or payload[key] is None:
        return None
    return require_dict(payload, key)


def dumps_stable(value: Any) -> bytes:
    """Return a byte-stable JSON encoding of ``value``.

    Pins compact separators and sorted keys so the resulting bytes are
    identical across runs and processes. The crypto layer hashes these
    payloads — any drift in formatting changes the hash.

    Returns UTF-8 bytes (the wire encoding); callers that need a string
    can ``.decode("utf-8")``.
    """
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
