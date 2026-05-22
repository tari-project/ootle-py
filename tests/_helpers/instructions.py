"""Helpers for inspecting decoded transaction-instruction JSON in tests."""

from __future__ import annotations

from typing import Any, cast


def kinds_and_methods(instructions: list[Any]) -> tuple[list[str], list[str]]:
    """Return each instruction's variant key and every ``CallMethod`` method name.

    ``instructions`` is a decoded ``body["instructions"]`` list — a mix of
    bare strings (no-payload variants) and single-key dicts.
    """
    kinds: list[str] = []
    methods: list[str] = []
    for ins in instructions:
        if isinstance(ins, str):
            kinds.append(ins)
            continue
        if not isinstance(ins, dict):
            continue
        ins_dict = cast("dict[str, Any]", ins)
        kinds.append(next(iter(ins_dict)))
        cm = ins_dict.get("CallMethod")
        if isinstance(cm, dict):
            method = cast("dict[str, Any]", cm).get("method")
            if isinstance(method, str):
                methods.append(method)
    return kinds, methods
