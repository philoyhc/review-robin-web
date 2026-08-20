"""Roster-CSV friendly-label transport (Segment 19C Item 1).

The reviewer / reviewee / relationships tag friendly labels round-trip
through the **roster CSV header** as a ``<Column>.<label>`` suffix
(e.g. ``ReviewerTag1.Tutor``) — the sole carrier. This module is the
shared translation layer both directions use:

- **Import** — ``normalize_headers`` splits a raw header row into the
  bare canonical column names (so ``csv.DictReader`` + the existing
  missing-column checks are unchanged) plus the captured
  ``(source_type, source_field) -> label`` overrides.
- **Export** — ``labeled_header`` re-attaches each slot's operator
  override to its column so a downloaded roster reproduces the labels.

Internal storage is unchanged: labels live in ``session_field_labels``
and resolve through ``app.services.field_labels``. This module only
moves them on and off the CSV header. Only the nine renamable tag /
pair-context slots participate; every other column passes through
untouched. Observer tags are out of scope (no friendly-label
affordance by design).

See ``guide/segment_19C_refinements.md`` Item 1.
"""

from __future__ import annotations

from app.db.models import ReviewSession
from app.services import field_labels

# Roster CSV tag-column header -> renamable friendly-label slot
# ``(source_type, source_field)``. Exactly the nine slots
# ``field_labels._VALID_SOURCE_FIELDS`` accepts; the identity columns
# (ReviewerName / RevieweeEmail / …) are not renamable and never split.
_LABELABLE_COLUMNS: dict[str, tuple[str, str]] = {
    "ReviewerTag1": ("reviewer", "tag_1"),
    "ReviewerTag2": ("reviewer", "tag_2"),
    "ReviewerTag3": ("reviewer", "tag_3"),
    "RevieweeTag1": ("reviewee", "tag_1"),
    "RevieweeTag2": ("reviewee", "tag_2"),
    "RevieweeTag3": ("reviewee", "tag_3"),
    "PairContextTag1": ("pair_context", "1"),
    "PairContextTag2": ("pair_context", "2"),
    "PairContextTag3": ("pair_context", "3"),
}

# Reverse map: slot -> canonical CSV column, for export.
_COLUMN_FOR_SLOT: dict[tuple[str, str], str] = {
    slot: column for column, slot in _LABELABLE_COLUMNS.items()
}


def split_header(cell: str) -> tuple[str, str | None]:
    """Split one raw header cell into ``(canonical_column, label)``.

    Only the nine labelable tag columns are split, and only on the
    **first** period — so a label may itself contain periods
    (``ReviewerTag1.Dept. Head`` → ``("ReviewerTag1", "Dept. Head")``).
    Every other cell (identity columns, unknown columns, columns that
    merely happen to contain a period) passes through unchanged with a
    ``None`` label.
    """
    head, sep, tail = cell.partition(".")
    if sep and head in _LABELABLE_COLUMNS:
        return head, tail
    return cell, None


def normalize_headers(
    raw_fieldnames: list[str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """Translate a raw header row into ``(canonical_fieldnames, captured)``.

    ``canonical_fieldnames`` drops any ``.label`` suffix so downstream
    ``DictReader`` row access and missing-column checks are unchanged.
    ``captured`` maps ``(source_type, source_field) -> label`` for every
    labelable column that carried a non-empty suffix; bare / absent
    columns simply don't appear (the caller clears those).
    """
    canonical: list[str] = []
    captured: dict[tuple[str, str], str] = {}
    for cell in raw_fieldnames:
        column, label = split_header(cell)
        canonical.append(column)
        if label is not None:
            stripped = label.strip()
            if stripped:
                captured[_LABELABLE_COLUMNS[column]] = stripped
    return canonical, captured


def labeled_header(
    review_session: ReviewSession, columns: tuple[str, ...]
) -> tuple[str, ...]:
    """Re-attach each labelable column's operator override for export.

    A column on its built-in default (no override) stays bare — the
    export never fabricates a ``Tag 1`` suffix — so a bare header on
    re-import round-trips cleanly to "no override".
    """
    out: list[str] = []
    for column in columns:
        slot = _LABELABLE_COLUMNS.get(column)
        if slot is not None:
            pair = field_labels.resolve_pair(review_session, *slot)
            if pair.has_override:
                out.append(f"{column}.{pair.friendly}")
                continue
        out.append(column)
    return tuple(out)
