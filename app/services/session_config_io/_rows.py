"""Row primitive + cell formatters for the Settings CSV.

``Row`` is the 3-column ``field,value,data_type`` tuple every
export / import row takes; the ``_str`` / ``_bool`` / ``_int`` /
``_decimal`` / ``_json`` formatters render a model value into a
cell string. The inverse cell *parsers* live in ``_apply.py``.
"""

from __future__ import annotations

import json
from typing import NamedTuple


class Row(NamedTuple):
    """One CSV row in the Settings export.

    ``field`` is a stable, dotted / bracketed key path; ``value``
    is the cell's string representation (empty cell ⇒ unset on
    import); ``data_type`` is the cell's parsing rule, descriptive
    of the cell only — independent of any underlying RTD's
    ``data_type``.
    """

    field: str
    value: str
    data_type: str


# Header row emitted on every export.
HEADER: tuple[str, str, str] = ("field", "value", "data_type")


# --------------------------------------------------------------------------- #
# Cell formatters
# --------------------------------------------------------------------------- #


def _str(value: str | None) -> str:
    if value is None:
        return ""
    return str(value)


def _bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)


def _decimal(value: float | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _json(value: object) -> str:
    """Compact, key-stable JSON. ``sort_keys=True`` keeps re-export
    bytes identical for the same logical content."""

    return json.dumps(value, separators=(",", ":"), sort_keys=True)
