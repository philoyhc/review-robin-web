"""Segment 20M Item 4 — group rows sort by the tags they show.

``_collapse_group_rows`` orders the groups by the values of the selected
tag display fields, in Band 3 order, compared as a tuple (the author's
example: TW01, Team 1 / TW01, Team 2 / TW45, Team 1), not by the boundary
key; a group showing no tag value falls back to its boundary key.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.web.routes_reviewer._surface import _collapse_group_rows


def _row(assignment_id: int, name: str, tags: tuple[str, str]) -> dict[str, Any]:
    cells = [
        {
            "field": SimpleNamespace(source_type="reviewee", source_field=f"tag_{slot}"),
            "label": label,
            "value": value,
        }
        for slot, label, value in ((1, "Group", tags[0]), (2, "Team", tags[1]))
    ]
    return {
        "assignment": SimpleNamespace(id=assignment_id, reviewee=SimpleNamespace(name=name)),
        "display_cells": cells,
        "sort_values": {},
    }


def test_the_groups_sort_by_their_shown_tags_in_band3_order() -> None:
    rows = [
        _row(1, "Aisha", ("TW45", "Team 1")),
        _row(2, "Ben", ("TW01", "Team 2")),
        _row(3, "Chen", ("TW01", "Team 1")),
    ]
    # The boundary keys would order them Aisha, Ben, Chen.
    keys = {1: ("A",), 2: ("B",), 3: ("C",)}
    collapsed = _collapse_group_rows(rows, group_key_by_assignment=keys)
    assert [r["group_identity"]["tag_line"] for r in collapsed] == [
        "TW01, Team 1",
        "TW01, Team 2",
        "TW45, Team 1",
    ]
    assert collapsed[0]["group_identity"]["tag_items"] == [
        {"label": "Group", "value": "TW01"},
        {"label": "Team", "value": "Team 1"},
    ]


def test_a_group_showing_no_tag_falls_back_to_its_boundary_key() -> None:
    rows = [_row(1, "Aisha", ("", "")), _row(2, "Ben", ("", ""))]
    collapsed = _collapse_group_rows(rows, group_key_by_assignment={1: ("Z",), 2: ("M",)})
    assert [r["group_identity"]["tag_line"] for r in collapsed] == ["M", "Z"]


def test_an_empty_tag_keeps_its_place_in_the_key() -> None:
    """A group with no Tutorial sorts on its empty Tutorial, not its Team
    shifted left into Tutorial's place."""
    rows = [
        _row(1, "Aisha", ("TW01", "Team 1")),
        _row(2, "Ben", ("", "Team 9")),
    ]
    collapsed = _collapse_group_rows(rows, group_key_by_assignment={1: ("A",), 2: ("B",)})
    assert [r["group_identity"]["tag_line"] for r in collapsed] == ["Team 9", "TW01, Team 1"]


def test_groups_showing_the_same_tags_fall_back_to_the_boundary_key() -> None:
    rows = [_row(1, "Aisha", ("TW01", "Team 1")), _row(2, "Ben", ("TW01", "Team 1"))]
    collapsed = _collapse_group_rows(rows, group_key_by_assignment={1: ("Z",), 2: ("M",)})
    assert [r["assignment"].id for r in collapsed] == [2, 1]
