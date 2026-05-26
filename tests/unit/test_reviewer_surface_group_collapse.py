"""Reviewer surface group-row composition (Segment 13C +
2026-05-26 follow-up).

The reviewer surface collapses a group-scoped instrument's
per-reviewee assignment rows into one row per boundary-defined
group. The collapsed row's identity cell composes a **tag line**
above + (optionally) the member names below.

Pre-2026-05-26 the tag line was built solely from the boundary
tag values (the values that defined group membership). That
silently dropped any non-boundary reviewee tag the operator
selected as a display field — the operator's Band 2 preview
showed every selected tag pill's value, but the reviewer surface
didn't. This test pins the post-fix contract: the tag line
includes the values of every visible ``reviewee.tag_*`` display
field on the instrument, comma-joined, in display order. Falls
back to the boundary-key composition when there are zero
reviewee.tag_* display fields (so the line is never blank when
a boundary tag value exists).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.web.routes_reviewer._surface import _collapse_group_rows


def _cell(source_type: str, source_field: str, value: str) -> dict:
    field = SimpleNamespace(
        source_type=source_type, source_field=source_field
    )
    return {"field": field, "label": source_field, "value": value, "is_profile_link": False}


def _row(
    assignment_id: int,
    reviewee_name: str,
    *,
    display_cells: list[dict],
) -> dict:
    assignment = SimpleNamespace(
        id=assignment_id, reviewee=SimpleNamespace(name=reviewee_name)
    )
    return {
        "assignment": assignment,
        "display_cells": list(display_cells),
        "sort_values": {},
    }


def test_collapse_includes_every_visible_reviewee_tag_in_tag_line() -> None:
    """Operator picked reviewee.tag_1 (the boundary) AND
    reviewee.tag_2 (non-boundary) as display fields. Both values
    surface in the tag line — matching the operator's Band 2
    preview."""
    rows = [
        _row(
            10,
            "Carol",
            display_cells=[
                _cell("reviewee", "tag_1", "Team A"),
                _cell("reviewee", "tag_2", "Junior"),
            ],
        ),
        _row(
            11,
            "Eve",
            display_cells=[
                _cell("reviewee", "tag_1", "Team A"),
                _cell("reviewee", "tag_2", "Senior"),
            ],
        ),
    ]
    collapsed = _collapse_group_rows(
        rows,
        group_key_by_assignment={10: ("Team A",), 11: ("Team A",)},
        name_visible=True,
    )
    assert len(collapsed) == 1
    identity = collapsed[0]["group_identity"]
    # Boundary-tag value comes first (Carol is the representative,
    # ordered by assignment id), non-boundary tag follows.
    assert identity["tag_line"] == "Team A, Junior"
    assert identity["member_names"] == ["Carol", "Eve"]


def test_collapse_skips_pair_context_tags_from_tag_line() -> None:
    """Pair-context tag display fields don't share at the group
    level (each pair has its own pair-context row). Only
    reviewee.tag_* values contribute to the tag line, matching
    the operator preview's filter."""
    rows = [
        _row(
            20,
            "Carol",
            display_cells=[
                _cell("reviewee", "tag_1", "Team A"),
                _cell("pair_context", "tag_1", "mentor"),
            ],
        ),
    ]
    collapsed = _collapse_group_rows(
        rows,
        group_key_by_assignment={20: ("Team A",)},
        name_visible=True,
    )
    assert collapsed[0]["group_identity"]["tag_line"] == "Team A"


def test_collapse_falls_back_to_boundary_key_when_no_tag_display_fields() -> None:
    """An instrument with zero visible ``reviewee.tag_*`` display
    fields keeps the legacy boundary-key tag line so the cell is
    never blank when a boundary tag value exists."""
    rows = [
        _row(
            30,
            "Carol",
            display_cells=[
                # Only the Name display field, no tags.
                _cell("reviewee", "name", "Carol"),
            ],
        ),
    ]
    collapsed = _collapse_group_rows(
        rows,
        group_key_by_assignment={30: ("Team A",)},
        name_visible=True,
    )
    assert collapsed[0]["group_identity"]["tag_line"] == "Team A"


def test_collapse_drops_empty_tag_values_from_tag_line() -> None:
    """A tag display field whose value is blank for the
    representative member is silently dropped from the tag line
    (matching the operator preview's ``join`` of non-empty values)."""
    rows = [
        _row(
            40,
            "Carol",
            display_cells=[
                _cell("reviewee", "tag_1", "Team A"),
                _cell("reviewee", "tag_2", ""),
                _cell("reviewee", "tag_3", "  "),
            ],
        ),
    ]
    collapsed = _collapse_group_rows(
        rows,
        group_key_by_assignment={40: ("Team A",)},
        name_visible=True,
    )
    assert collapsed[0]["group_identity"]["tag_line"] == "Team A"
