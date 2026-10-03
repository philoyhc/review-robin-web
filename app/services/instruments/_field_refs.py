"""An instrument's references to its own fields, carried across a copy.

``Instrument.sort_display_fields`` names display fields by id
(``{"display_field_id": N, "dir": ...}``), and ``Instrument.column_widths``
names display and response fields by id (``df_<id>`` / ``rf_<id>``). A
copy's fields get new ids, so every path that copies an instrument has
to re-point both: Replicate, session Duplicate and the settings import
(findings A28).

- ``repoint_sort`` / ``repoint_widths`` map old ids to new ones, given
  the copy's id maps (Replicate, Duplicate).
- ``sort_to_positions`` / ``widths_to_positions`` write ids as the
  fields' 1-based positions for the settings CSV, and
  ``sort_from_positions`` / ``widths_from_positions`` read them back
  against the imported fields. A position is the ``m`` of the field's
  ``display_fields[m]`` / ``response_fields[m]`` rows.

Throughout, the group-identity sentinel (``GROUP_IDENTITY_SORT_KEY``,
the composed Group column) names no field and is kept as it is, as is
any width key that names no field (``identity``). An entry or key that
names no field of the source is dropped.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.instruments._display_fields import GROUP_IDENTITY_SORT_KEY

__all__ = [
    "repoint_sort",
    "repoint_widths",
    "sort_to_positions",
    "sort_from_positions",
    "widths_to_positions",
    "widths_from_positions",
]

_WIDTH_KEY = re.compile(r"^(df|rf)_(\d+)$")
_WIDTH_POSITION_KEY = re.compile(r"^(df|rf)@(\d+)$")
_SORT_POSITION = "display_field"


def repoint_sort(
    entries: list[dict[str, Any]] | None, display_ids: dict[int, int]
) -> list[dict[str, Any]] | None:
    """Sort entries re-pointed at the copy's display fields."""
    if not isinstance(entries, list) or not entries:
        return entries if isinstance(entries, list) else None
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        old_id = entry.get("display_field_id")
        if old_id == GROUP_IDENTITY_SORT_KEY:
            out.append(dict(entry))
            continue
        new_id = display_ids.get(old_id) if isinstance(old_id, int) else None
        if new_id is not None:
            out.append({**entry, "display_field_id": new_id})
    return out


def repoint_widths(
    widths: dict[str, Any] | None,
    *,
    display_ids: dict[int, int],
    field_ids: dict[int, int],
) -> dict[str, Any] | None:
    """Column widths with ``df_<id>`` / ``rf_<id>`` keys re-pointed at
    the copy's fields."""
    if not isinstance(widths, dict) or not widths:
        return widths if isinstance(widths, dict) else None
    out: dict[str, Any] = {}
    for key, value in widths.items():
        match = _WIDTH_KEY.match(key) if isinstance(key, str) else None
        if match is None:
            out[key] = value
            continue
        ids = display_ids if match.group(1) == "df" else field_ids
        new_id = ids.get(int(match.group(2)))
        if new_id is not None:
            out[f"{match.group(1)}_{new_id}"] = value
    return out


def sort_to_positions(
    entries: list[dict[str, Any]] | None, display_positions: dict[int, int]
) -> list[dict[str, Any]]:
    """Sort entries for the settings CSV: ``display_field_id`` becomes
    ``display_field``, the field's 1-based position."""
    out: list[dict[str, Any]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        field_id = entry.get("display_field_id")
        if field_id == GROUP_IDENTITY_SORT_KEY:
            out.append(dict(entry))
            continue
        position = (
            display_positions.get(field_id) if isinstance(field_id, int) else None
        )
        if position is None:
            continue
        rest = {k: v for k, v in entry.items() if k != "display_field_id"}
        out.append({_SORT_POSITION: position, **rest})
    return out


def sort_from_positions(
    entries: list[Any] | None, display_ids_by_position: dict[int, int]
) -> list[dict[str, Any]]:
    """Sort entries from the settings CSV, re-pointed at the imported
    display fields. An older bundle's id-keyed entries name the source
    session's fields, which the import never has, so they are dropped."""
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        rest = {
            k: v
            for k, v in entry.items()
            if k not in (_SORT_POSITION, "display_field_id")
        }
        if entry.get("display_field_id") == GROUP_IDENTITY_SORT_KEY:
            new_id = GROUP_IDENTITY_SORT_KEY
        else:
            position = entry.get(_SORT_POSITION)
            # ``bool`` is an ``int`` subclass; ``true`` is no position.
            is_position = isinstance(position, int) and not isinstance(
                position, bool
            )
            new_id = (
                display_ids_by_position.get(position) if is_position else None
            )
        # A hand-edited file can name one field twice; the operator's
        # own setter refuses that, so keep the first.
        if new_id is None or new_id in seen:
            continue
        seen.add(new_id)
        out.append({"display_field_id": new_id, **rest})
    return out


def widths_to_positions(
    widths: dict[str, Any] | None,
    *,
    display_positions: dict[int, int],
    field_positions: dict[int, int],
) -> dict[str, Any]:
    """Column widths for the settings CSV: ``df_<id>`` / ``rf_<id>``
    become ``df@<position>`` / ``rf@<position>``."""
    out: dict[str, Any] = {}
    for key, value in (widths if isinstance(widths, dict) else {}).items():
        match = _WIDTH_KEY.match(key) if isinstance(key, str) else None
        if match is None:
            out[key] = value
            continue
        positions = (
            display_positions if match.group(1) == "df" else field_positions
        )
        position = positions.get(int(match.group(2)))
        if position is not None:
            out[f"{match.group(1)}@{position}"] = value
    return out


def widths_from_positions(
    widths: dict[str, Any] | None,
    *,
    display_ids_by_position: dict[int, int],
    field_ids_by_position: dict[int, int],
) -> dict[str, Any] | None:
    """Column widths from the settings CSV, re-pointed at the imported
    fields. An older bundle's ``df_<id>`` / ``rf_<id>`` keys name the
    source session's fields and are dropped."""
    if not isinstance(widths, dict):
        return None
    out: dict[str, Any] = {}
    for key, value in widths.items():
        if not isinstance(key, str) or _WIDTH_KEY.match(key):
            continue
        match = _WIDTH_POSITION_KEY.match(key)
        if match is None:
            out[key] = value
            continue
        ids = (
            display_ids_by_position
            if match.group(1) == "df"
            else field_ids_by_position
        )
        new_id = ids.get(int(match.group(2)))
        if new_id is not None:
            out[f"{match.group(1)}_{new_id}"] = value
    return out or None
