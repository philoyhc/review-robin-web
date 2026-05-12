"""Reviewer-surface sort helper — Segment 13B PR 1.

Pure function that consumes the operator-default sort spec stored
on ``Instrument.sort_display_fields`` (the canonical
``[{"display_field_id": int, "dir": "asc"|"desc"}, ...]`` shape
per ``spec/sort_by_reviewee.md``) and orders a list of
reviewer-surface rows accordingly.

Render-time invariants (per spec):

- **NULL handling:** rows whose sort-key value is ``None`` sort
  **last** regardless of direction. Operators sort to surface
  rows with data; "no data" should never bubble to the top.
- **Render-time defense:** sort-spec entries whose
  ``display_field_id`` no longer references a real display field
  (e.g. operator deleted the field after configuring sort) skip
  silently. The render falls through to the next-priority slot,
  then to insertion order.
- **Cascade:** multi-key sort cascades by list order — first
  entry primary, second secondary, third tertiary. Up to 3 keys
  per the service-layer validator.
- **Stable:** rows that tie on every sort key (or empty
  sort_spec) keep their input order.

The helper is decoupled from the row shape: callers hand in a
``key_resolver`` callable that maps
``(row, display_field_id) -> value`` so the helper stays
content-agnostic. Routes wire the resolver against whatever
shape ``rows_by_instrument`` produces.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any, TypeVar

__all__ = [
    "decode_cookie_sort_spec_for_reviewer_surface",
    "order_rows_by_sort_spec",
]


# Segment 13B Part 2 PR 5 — cookie shape.
#
# The client-side primitive in ``base.html`` writes
# ``[{"key": "...", "dir": "asc|desc"}, ...]`` JSON into a cookie
# named by the ``data-rrw-sortable`` table marker. Per-surface
# helpers below decode the opaque ``key`` strings into the
# per-surface natural shape so the server-side
# ``order_rows_by_sort_spec`` helper can render the right initial
# order without waiting for the JS to re-shuffle.

# Cookie name convention:
#   ``rrw-sort-rs-{session_id}-{instrument_id}`` for the reviewer surface.
#   ``rrw-sort-{surface}-{session_id}`` for operator setup tables.
_REVIEWER_COOKIE_PREFIX = "rrw-sort-rs"


def decode_cookie_sort_spec_for_reviewer_surface(
    *,
    cookies: dict[str, str],
    session_id: int,
    instrument_id: int,
    display_fields,
) -> list[dict[str, object]] | None:
    """Translate the reviewer-surface cookie into a
    ``sort_display_fields``-shaped spec the
    ``order_rows_by_sort_spec`` helper understands.

    Returns ``None`` when no cookie exists (caller falls back to
    the operator-default ``instrument.sort_display_fields``). An
    empty list means "operator default is overridden but the
    reviewer cleared the sort" — distinct from ``None`` so the
    caller can honour the override.

    Opaque keys decoded:

    - ``reviewee.name`` →
      locked Name display field's ``display_field_id``.
    - ``reviewee.email_or_identifier`` → locked Email display
      field's ``display_field_id``.
    - ``display:N`` → ``int(N)``.
    - ``response:N`` → dropped (server doesn't sort by response
      values; the JS re-sorts client-side if any).

    Malformed JSON / missing keys / unknown ``dir`` values are
    silently filtered. Per ``spec/sort_by_reviewee.md`` and the
    primitive's hard cap, at most 3 entries.
    """
    import json

    cookie_name = (
        f"{_REVIEWER_COOKIE_PREFIX}-{session_id}-{instrument_id}"
    )
    raw = cookies.get(cookie_name)
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(decoded, list):
        return None
    name_id_by_source = {
        df.source_field: df.id
        for df in display_fields
        if df.source_type == "reviewee"
    }
    display_ids = {df.id for df in display_fields}
    out: list[dict[str, object]] = []
    for entry in decoded[:3]:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        direction = entry.get("dir")
        if direction not in ("asc", "desc"):
            continue
        df_id: int | None = None
        if key == "reviewee.name":
            df_id = name_id_by_source.get("name")
        elif key == "reviewee.email_or_identifier":
            df_id = name_id_by_source.get("email_or_identifier")
        elif isinstance(key, str) and key.startswith("display:"):
            try:
                candidate = int(key.split(":", 1)[1])
            except ValueError:
                continue
            if candidate in display_ids:
                df_id = candidate
        # ``response:N`` and any other opaque keys → skip (server
        # can't sort by response values).
        if df_id is None:
            continue
        out.append({"display_field_id": df_id, "dir": direction})
    return out


Row = TypeVar("Row")


def order_rows_by_sort_spec(
    rows: Iterable[Row],
    sort_spec: Sequence[dict[str, Any]] | None,
    *,
    key_resolver: Callable[[Row, int], Any],
    known_display_field_ids: set[int] | None = None,
) -> list[Row]:
    """Order ``rows`` per ``sort_spec``, returning a new list.

    ``sort_spec`` is the value stored on
    ``Instrument.sort_display_fields`` — ``None`` or ``[]`` both
    mean "no operator default", in which case the rows are
    returned in input order.

    ``key_resolver(row, display_field_id) -> value`` extracts the
    sortable value for one display field. The helper compares
    values pairwise via the spec's direction; ``None`` always
    sorts last regardless of direction.

    ``known_display_field_ids`` is the set of IDs the caller
    recognises as still-existing display fields on the instrument.
    Sort-spec entries whose ``display_field_id`` isn't in this
    set drop out — render-time defense against stale references
    (operator deleted a display field after configuring sort).
    Passing ``None`` skips the filter (helper assumes the caller
    already validated the spec).
    """
    materialised = list(rows)
    if not sort_spec:
        return materialised

    # Filter out entries pointing at no-longer-existing display
    # fields. Cascade falls through to the next slot, then to
    # insertion order — exactly what stable sort with an empty
    # spec yields.
    effective_spec: list[dict[str, Any]] = []
    for entry in sort_spec:
        field_id = entry.get("display_field_id")
        direction = entry.get("dir", "asc")
        if not isinstance(field_id, int):
            continue
        if (
            known_display_field_ids is not None
            and field_id not in known_display_field_ids
        ):
            continue
        if direction not in ("asc", "desc"):
            continue
        effective_spec.append(entry)

    if not effective_spec:
        return materialised

    def _row_key(row: Row) -> tuple:
        keys: list[tuple[int, Any]] = []
        for entry in effective_spec:
            field_id = entry["display_field_id"]
            value = key_resolver(row, field_id)
            descending = entry["dir"] == "desc"
            # NULL sorts last regardless of direction: emit a
            # (1, ?) tuple for None and (0, value) otherwise so
            # the tuple compare lands None at the end on both
            # asc and desc. For desc, we still want None last —
            # so we don't flip the (0/1) flag, only the value
            # within the bucket.
            if value is None:
                # ``None`` always-last sentinel.
                keys.append((1, 0))
            else:
                # Bucket 0 = "has value". Compare values
                # naturally; for descending order invert via the
                # comparable-negation pattern. We avoid mutating
                # the value into a different type — instead the
                # caller passes through whatever's already
                # comparable, and we use a stable wrapper.
                if descending:
                    keys.append((0, _DescendingKey(value)))
                else:
                    keys.append((0, value))
        return tuple(keys)

    return sorted(materialised, key=_row_key)


class _DescendingKey:
    """Wrap a sortable value so that natural-order comparisons
    invert. Used internally by ``order_rows_by_sort_spec`` to
    realise descending direction without copying / mutating the
    underlying value.

    Falls back to string comparison when the underlying value
    types are mixed (e.g. operator's sort key references a
    display field that contains both ints and None — handled at
    the row level — and mixed strings/ints — coerced here).
    """

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: "_DescendingKey") -> bool:
        try:
            return self.value > other.value
        except TypeError:
            # Mixed-type comparison — coerce to string. Stable but
            # operator-visible only if mixed types end up on the
            # same column, which the spec doesn't anticipate.
            return str(self.value) > str(other.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _DescendingKey):
            return self.value == other.value
        return NotImplemented
