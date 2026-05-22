"""Shared JSON-extraction helpers for the ``_types/*_json.py`` parsers.

Centralised so the four sibling parsers (``_json``, ``_indexer_json``,
``_reject_reason_json``, ``_substate_json``) share one error-message
format and one type contract. The module name is underscore-prefixed
to keep these helpers package-private — they are an implementation
detail of the parsers and must not leak into the public API.
"""

from __future__ import annotations

from typing import Any, cast


def require_str(payload: dict[str, Any], key: str) -> str:
    """Return ``payload[key]``, raising ``TypeError`` if it is not a string."""
    value = payload[key]
    if not isinstance(value, str):
        msg = f"field {key!r} must be a string, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def require_int(payload: dict[str, Any], key: str) -> int:
    """Return ``payload[key]``, raising ``TypeError`` if it is not an ``int``.

    Rejects ``bool`` (Python's ``bool`` is a subclass of ``int``) so wire
    shapes that distinguish the two stay disambiguated.
    """
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"field {key!r} must be an int, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``payload[key]``, raising ``TypeError`` if it is not a dict."""
    value = payload[key]
    if not isinstance(value, dict):
        msg = f"field {key!r} must be an object, got {type(value).__name__}"
        raise TypeError(msg)
    return cast("dict[str, Any]", value)


def optional_dict(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    """Return ``payload[key]`` when present as a dict; ``None`` when absent.

    Raises ``TypeError`` if the key is present but not a dict.
    """
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        msg = f"field {key!r} must be an object when present"
        raise TypeError(msg)
    return cast("dict[str, Any]", value)


def optional_list(payload: dict[str, Any], key: str) -> list[Any] | None:
    """Return ``payload[key]`` when present as a list; ``None`` when absent.

    Raises ``TypeError`` if the key is present but not a list.
    """
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        msg = f"field {key!r} must be an array when present"
        raise TypeError(msg)
    return cast("list[Any]", value)


def as_dict(value: Any) -> dict[str, Any]:
    """Coerce ``value`` to ``dict[str, Any]``, raising ``TypeError`` otherwise."""
    if not isinstance(value, dict):
        msg = f"expected an object, got {type(value).__name__}"
        raise TypeError(msg)
    return cast("dict[str, Any]", value)


def as_str(value: Any) -> str:
    """Coerce ``value`` to ``str``, raising ``TypeError`` otherwise."""
    if not isinstance(value, str):
        msg = f"expected a string, got {type(value).__name__}"
        raise TypeError(msg)
    return value
