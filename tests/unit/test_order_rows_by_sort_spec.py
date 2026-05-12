"""Unit tests for ``views.order_rows_by_sort_spec`` —
Segment 13B PR 1.

Pure-function helper that orders reviewer-surface rows per the
operator's sort spec. Covers cascade + NULL-last + render-time
defense for stale display-field IDs + asc/desc inversion.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.web.views import order_rows_by_sort_spec


@dataclass(frozen=True)
class _Row:
    """Stand-in for a reviewer-surface row dict — just enough
    shape for the test resolver."""

    rid: int
    values: dict[int, object | None]


def _resolver(row: _Row, display_field_id: int) -> object | None:
    return row.values.get(display_field_id)


# --- No-op paths ----------------------------------------------------------


def test_empty_spec_returns_input_order() -> None:
    rows = [_Row(1, {7: "b"}), _Row(2, {7: "a"})]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, [], key_resolver=_resolver
    )] == [1, 2]


def test_none_spec_returns_input_order() -> None:
    rows = [_Row(1, {7: "b"}), _Row(2, {7: "a"})]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, None, key_resolver=_resolver
    )] == [1, 2]


# --- Single-key sort ------------------------------------------------------


def test_single_key_asc() -> None:
    rows = [_Row(1, {7: "b"}), _Row(2, {7: "a"}), _Row(3, {7: "c"})]
    spec = [{"display_field_id": 7, "dir": "asc"}]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [2, 1, 3]


def test_single_key_desc() -> None:
    rows = [_Row(1, {7: "b"}), _Row(2, {7: "a"}), _Row(3, {7: "c"})]
    spec = [{"display_field_id": 7, "dir": "desc"}]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [3, 1, 2]


# --- NULL handling --------------------------------------------------------


def test_null_values_sort_last_under_asc() -> None:
    rows = [
        _Row(1, {7: "b"}),
        _Row(2, {7: None}),
        _Row(3, {7: "a"}),
    ]
    spec = [{"display_field_id": 7, "dir": "asc"}]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [3, 1, 2]


def test_null_values_sort_last_under_desc() -> None:
    """Per spec §"NULL handling": NULLs sort last regardless of
    direction. Operators sort to surface rows with data."""
    rows = [
        _Row(1, {7: "b"}),
        _Row(2, {7: None}),
        _Row(3, {7: "a"}),
    ]
    spec = [{"display_field_id": 7, "dir": "desc"}]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [1, 3, 2]


# --- Multi-key cascade ----------------------------------------------------


def test_two_key_cascade() -> None:
    """Tie on primary key falls through to secondary."""
    rows = [
        _Row(1, {7: "a", 9: "z"}),
        _Row(2, {7: "a", 9: "y"}),
        _Row(3, {7: "b", 9: "x"}),
    ]
    spec = [
        {"display_field_id": 7, "dir": "asc"},
        {"display_field_id": 9, "dir": "asc"},
    ]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [2, 1, 3]


def test_three_key_cascade_with_mixed_directions() -> None:
    rows = [
        _Row(1, {7: "a", 9: "x", 11: 1}),
        _Row(2, {7: "a", 9: "x", 11: 3}),
        _Row(3, {7: "a", 9: "x", 11: 2}),
    ]
    spec = [
        {"display_field_id": 7, "dir": "asc"},
        {"display_field_id": 9, "dir": "asc"},
        {"display_field_id": 11, "dir": "desc"},
    ]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [2, 3, 1]


# --- Render-time defense ---------------------------------------------------


def test_unknown_display_field_id_skipped() -> None:
    """A sort-spec entry referencing a display field that no
    longer exists on the instrument silently drops; the next
    slot becomes primary."""
    rows = [
        _Row(1, {9: "b"}),
        _Row(2, {9: "a"}),
    ]
    spec = [
        {"display_field_id": 999, "dir": "asc"},  # stale
        {"display_field_id": 9, "dir": "asc"},
    ]
    out = order_rows_by_sort_spec(
        rows,
        spec,
        key_resolver=_resolver,
        known_display_field_ids={9},
    )
    assert [r.rid for r in out] == [2, 1]


def test_all_entries_stale_falls_back_to_insertion_order() -> None:
    rows = [_Row(1, {7: "b"}), _Row(2, {7: "a"})]
    spec = [{"display_field_id": 999, "dir": "asc"}]
    out = order_rows_by_sort_spec(
        rows,
        spec,
        key_resolver=_resolver,
        known_display_field_ids={7},
    )
    assert [r.rid for r in out] == [1, 2]


def test_known_ids_none_skips_filter() -> None:
    """Passing ``known_display_field_ids=None`` means the caller
    has already validated the spec — every entry runs."""
    rows = [_Row(1, {9: "b"}), _Row(2, {9: "a"})]
    spec = [{"display_field_id": 9, "dir": "asc"}]
    out = order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver, known_display_field_ids=None
    )
    assert [r.rid for r in out] == [2, 1]


# --- Stability ------------------------------------------------------------


def test_rows_tied_on_every_key_keep_input_order() -> None:
    """Stable sort: rows that tie on every sort key keep their
    input order."""
    rows = [
        _Row(1, {7: "a"}),
        _Row(2, {7: "a"}),
        _Row(3, {7: "a"}),
    ]
    spec = [{"display_field_id": 7, "dir": "asc"}]
    assert [r.rid for r in order_rows_by_sort_spec(
        rows, spec, key_resolver=_resolver
    )] == [1, 2, 3]


def test_bad_dir_entries_skipped() -> None:
    rows = [_Row(1, {7: "b"}), _Row(2, {7: "a"})]
    spec = [{"display_field_id": 7, "dir": "sideways"}]
    out = order_rows_by_sort_spec(rows, spec, key_resolver=_resolver)
    # Invalid dir → entry drops; input order preserved.
    assert [r.rid for r in out] == [1, 2]
