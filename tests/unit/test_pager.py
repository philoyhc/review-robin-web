"""``views.build_pager`` — Segment 19J.5.

The arithmetic is small and entirely boundary conditions, which is
exactly the shape that ships wrong: an off-by-one here shows up as a
roster row nobody can reach, and no other test in the suite would
notice.

The four **elision** tests that used to sit here retired with the code
they covered (19J.9, 2026-09-11): ``Pager`` no longer computes a
five-wide window, First / Last anchors or ellipsis flags, because the
strip that rendered them is gone and the cluster shows every range.
What is left is what never depended on the strip — where the ranges
fall, and what an out-of-range offset does.
"""
from __future__ import annotations

import pytest

from app.web import views


def _labels(pager: views.Pager) -> list[str]:
    return [link.label for link in pager.ranges]


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
    current = [link for link in pager.ranges if link.is_current]
    assert len(current) == 1
    assert current[0].label == "201–400"


def test_a_large_table_is_every_range_not_a_window() -> None:
    """What replaced elision. The strip capped its own width at five
    and left its reach at two pages a click; the menu holds the lot, so
    the middle of a 40,000-row table is one move away."""
    pager = views.build_pager(total=40000, offset=20000)
    assert len(pager.ranges) == 200
    assert pager.ranges[0].label == "1–200"
    assert pager.ranges[-1].label == "39,801–40,000"


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
    assert pager.offset == 400
    current = [link for link in pager.ranges if link.is_current]
    assert current[0].label == "401–556"


def test_the_pager_carries_only_what_the_cluster_reads() -> None:
    """The retirement, pinned.

    ``links``, ``first``, ``last`` and the two ``elided_*`` flags were
    the strip's. Leaving them as unread fields is how a reader comes to
    believe there is still a window somewhere deciding what renders.
    """
    pager = views.build_pager(total=40000, offset=20000)
    assert {f for f in pager.__dataclass_fields__} == {
        "offset", "page_size", "total"
    }


# --------------------------------------------------------------------- #
# All seven pages, not four
#
# Every roster-bearing table gets the same pager. A page left out would
# look fine on its own and be found months later by the operator who
# needed row 900 on exactly that page, so the set is pinned here rather
# than trusted to the diff.
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

#: 19J.9 rung 2 retired ``_preview_pager.html`` — the range strip —
#: and the cluster took its two render sites. The contract these three
#: tests pin is unchanged: every roster page, twice, above the count
#: line.
_PARTIAL = "operator/partials/_pager_cluster.html"


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_every_roster_page_includes_the_pager_twice(page: str) -> None:
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    assert src.count(_PARTIAL) == 2, f"{page}: expected the pager above and below"


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_second_copy_carries_the_bottom_modifier(page: str) -> None:
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    assert src.count(
        'cluster_extra_class = "table-pager-cluster-bottom"'
    ) == 1


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_strip_it_replaced_is_gone(page: str) -> None:
    """The retirement, pinned per page.

    Leaving one template still including the strip would put two pagers
    on that page and nowhere else — the state 19J.9 was explicit about
    not leaving behind, and the kind that survives a diff read.
    """
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    assert "_preview_pager.html" not in src
    assert 'pager_extra_class = "table-pager-bottom"' not in src


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_pager_sits_with_the_count_line_it_replaces(page: str) -> None:
    """Above the table, at the position 19I Item 10 chose for the count
    sentence — so the two never appear in different places."""
    src = (OPERATOR_TEMPLATES / page).read_text(encoding="utf-8")
    first_pager = src.index(_PARTIAL)
    count_line = src.index("operator/partials/_preview_count_line.html")
    assert first_pager < count_line


# ---------------------------------------------------------------------------
# ``Pager.ranges`` — Segment 19J Item 9. Derived on demand rather than
# stored: the ranges are markup's business, and a 40,000-row table has
# 200 of them. Added at rung 1 as ``all_ranges``, beside 19J.5's
# ``links``; renamed when rung 2's follow-up retired the window, since
# there is no longer a partial list to distinguish it from.


def test_ranges_covers_the_whole_table() -> None:
    pager = views.build_pager(total=1401, offset=0)
    assert pager is not None

    ranges = pager.ranges
    assert len(ranges) == 8  # 1,401 rows at 200 a page
    assert [r.label for r in ranges][:2] == ["1–200", "201–400"]
    assert ranges[-1].label == "1,401–1,401"
    assert [r.offset for r in ranges] == [i * 200 for i in range(8)]


def test_ranges_marks_the_current_page_and_only_that_one() -> None:
    pager = views.build_pager(total=40000, offset=20000)
    assert pager is not None

    current = [r for r in pager.ranges if r.is_current]
    assert len(current) == 1
    assert current[0].offset == 20000
    # And it agrees with the offset the pager was built at, which is
    # what the menu's summary renders.
    assert current[0].offset == pager.offset
    assert current[0].label == "20,001–20,200"


def test_ranges_marks_the_current_page_after_a_clamp() -> None:
    """``build_pager`` snaps an arbitrary offset onto a boundary, and
    the menu has to agree with where it landed rather than with what was
    asked for."""
    pager = views.build_pager(total=1401, offset=1399)
    assert pager is not None

    current = [r for r in pager.ranges if r.is_current]
    assert len(current) == 1
    assert current[0].offset == 1200
