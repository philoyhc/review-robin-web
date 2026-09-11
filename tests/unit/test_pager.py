"""``views.build_pager`` — Segment 19J.5.

The arithmetic is small and entirely boundary conditions, which is
exactly the shape that ships wrong: an off-by-one here shows up as a
roster row nobody can reach, and no other test in the suite would
notice.
"""
from __future__ import annotations

import pytest

from app.web import views


def _labels(pager: views.Pager) -> list[str]:
    return [link.label for link in pager.links]


# --------------------------------------------------------------------- #
# One page is no pager
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("total", [0, 1, 199, 200])
def test_a_table_that_fits_gets_no_pager(total: int) -> None:
    """Same rule as ``preview_count_line``'s quiet case: a control that
    cannot go anywhere is noise."""
    assert views.build_pager(total=total) is None


def test_one_row_over_the_page_size_gets_a_pager() -> None:
    pager = views.build_pager(total=201)
    assert pager is not None
    assert _labels(pager) == ["1–200", "201–201"]


# --------------------------------------------------------------------- #
# Ranges
# --------------------------------------------------------------------- #


def test_ranges_are_inclusive_and_the_last_one_stops_at_the_total() -> None:
    pager = views.build_pager(total=556)
    assert _labels(pager) == ["1–200", "201–400", "401–556"]


def test_an_exact_multiple_does_not_produce_an_empty_final_page() -> None:
    pager = views.build_pager(total=400)
    assert _labels(pager) == ["1–200", "201–400"]


def test_labels_carry_thousands_separators() -> None:
    pager = views.build_pager(total=40000, offset=20000)
    assert "20,001–20,200" in _labels(pager)


def test_exactly_one_range_is_current() -> None:
    pager = views.build_pager(total=556, offset=200)
    current = [link for link in pager.links if link.is_current]
    assert len(current) == 1
    assert current[0].label == "201–400"


# --------------------------------------------------------------------- #
# Elision — a 40,000-row table must not be 200 links wide
# --------------------------------------------------------------------- #


def test_a_large_table_shows_a_window_with_first_and_last_hung_off_the_ends() -> None:
    pager = views.build_pager(total=40000, offset=20000)
    assert len(pager.links) == 5
    assert pager.first.label == "1–200"
    assert pager.last.label == "39,801–40,000"
    assert pager.elided_before and pager.elided_after


def test_no_first_anchor_when_the_window_already_starts_at_the_top() -> None:
    """A First link pointing at a range the strip already shows would be
    two ways to reach the same place."""
    pager = views.build_pager(total=40000, offset=0)
    assert pager.first is None
    assert pager.links[0].label == "1–200"
    assert pager.last is not None


def test_no_last_anchor_when_the_window_already_reaches_the_end() -> None:
    pager = views.build_pager(total=40000, offset=39800)
    assert pager.last is None
    assert pager.links[-1].label == "39,801–40,000"
    assert pager.first is not None


def test_the_window_keeps_its_width_at_the_last_page() -> None:
    """Re-anchored rather than allowed to shrink, so the strip does not
    change width as the operator walks to the end."""
    pager = views.build_pager(total=40000, offset=39800)
    assert len(pager.links) == 5


# --------------------------------------------------------------------- #
# Clamping — a stale link is not an error page
# --------------------------------------------------------------------- #


def test_an_offset_past_the_end_lands_on_the_last_page() -> None:
    assert views.clamp_offset(99999, total=556) == 400


def test_a_negative_offset_lands_on_the_first_page() -> None:
    assert views.clamp_offset(-50, total=556) == 0


def test_an_offset_mid_page_snaps_down_to_its_boundary() -> None:
    assert views.clamp_offset(250, total=556) == 200


def test_clamping_an_empty_table_is_zero_not_a_crash() -> None:
    assert views.clamp_offset(400, total=0) == 0


def test_build_pager_clamps_rather_than_trusting_its_caller() -> None:
    pager = views.build_pager(total=556, offset=99999)
    current = [link for link in pager.links if link.is_current]
    assert current[0].label == "401–556"


# --------------------------------------------------------------------- #
# All seven pages, not four
#
# The scaffold's whole point is that every roster-bearing table gets the
# same strip. A page left out would look fine on its own and be found
# months later by the operator who needed row 900 on exactly that page,
# so the set is pinned here rather than trusted to the diff.
# --------------------------------------------------------------------- #

from pathlib import Path  # noqa: E402

OPERATOR_TEMPLATES = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "templates" / "operator"
)

# The seven pages that carry a roster table, named in 19J.5's Decision.
ROSTER_PAGES = [
    "session_reviewers.html",
    "session_reviewees.html",
    "session_relationships.html",
    "session_observers.html",
    "session_assignments.html",
    "session_invitations.html",
    "session_responses.html",
]

_PARTIAL = "operator/partials/_preview_pager.html"


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_every_roster_page_includes_the_pager_twice(page: str) -> None:
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    assert src.count(_PARTIAL) == 2, f"{page}: expected the pager above and below"


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_second_copy_carries_the_bottom_modifier(page: str) -> None:
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    assert src.count('pager_extra_class = "table-pager-bottom"') == 1


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_pager_sits_with_the_count_line_it_replaces(page: str) -> None:
    """Above the table, at the position 19I Item 10 chose for the count
    sentence — so the two never appear in different places."""
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    first_pager = src.index(_PARTIAL)
    count_line = src.index("operator/partials/_preview_count_line.html")
    assert first_pager < count_line
