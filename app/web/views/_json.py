"""Typed boundaries for JSON the view adapters read (segment 22E).

A JSON column or an audit ``detail`` may hold a shape its mapping does
not declare (a legacy or hand-written row), so the adapters keep their
shape checks; these helpers make each check once and hand back a typed
value.
"""

from __future__ import annotations

from typing import cast

__all__ = ["json_list", "json_object"]


def json_object(value: object) -> dict[str, object] | None:
    """``value`` as a JSON object, or ``None`` when it is not one."""
    if not isinstance(value, dict):
        return None
    return cast("dict[str, object]", value)


def json_list(value: object) -> list[object] | None:
    """``value`` as a JSON array, or ``None`` when it is not one."""
    if not isinstance(value, list):
        return None
    return cast("list[object]", value)
