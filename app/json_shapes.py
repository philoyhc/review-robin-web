"""Typed boundaries for JSON read back from a column, an audit
``detail`` or a request body (segment 22F).

Such a value may hold a shape its mapping does not declare (a legacy or
hand-written row, a client's body), so callers keep their shape checks;
these helpers make each check once and hand back a typed value. They sit
at the package root so services and the web layer share one copy.
"""

from __future__ import annotations

from typing import cast

__all__ = ["json_list", "json_object"]


def json_object(value: object) -> dict[str, object] | None:
    """``value`` as a JSON object (so its keys are strings), or ``None``
    when it is not one."""
    if not isinstance(value, dict):
        return None
    return cast("dict[str, object]", value)


def json_list(value: object) -> list[object] | None:
    """``value`` as a JSON array (its items any JSON value), or ``None``
    when it is not one."""
    if not isinstance(value, list):
        return None
    return cast("list[object]", value)
