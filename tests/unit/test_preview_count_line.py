"""The four branches of the shared preview-count sentence —
Segment 19I Item 10.

The sentence exists because a table's visible rows can fall short of
the whole roster for two unrelated reasons, and the page that
conflates them misleads. A filter *excluded* rows; a cap *withheld*
them. Only the second is something the operator can do anything
about, and only the second earns "more not shown".

Every assertion here pins one of those distinctions, so a rewrite
that collapses them fails rather than quietly shipping.
"""
from __future__ import annotations

import pytest

from app.web.views import preview_count_line


# --------------------------------------------------------------------------- #
# The quiet case.
# --------------------------------------------------------------------------- #


def test_nothing_trimmed_renders_nothing() -> None:
    """`Showing 6 of 6 reviewers.` is noise — a table showing
    everything needs no caption. Predates Item 10 (Item 4 set it);
    pinned here because the helper now owns it."""
    assert (
        preview_count_line(shown=6, matching=6, total=6, noun="reviewers")
        is None
    )


def test_the_quiet_case_holds_at_zero_rows() -> None:
    """An empty roster is not a trimmed one."""
    assert (
        preview_count_line(shown=0, matching=0, total=0, noun="reviewers")
        is None
    )


# --------------------------------------------------------------------------- #
# Filter branch — rows excluded, nothing withheld.
# --------------------------------------------------------------------------- #


def test_filtered_under_the_cap_says_neither_first_nor_withheld() -> None:
    line = preview_count_line(
        shown=3, matching=3, total=1240, noun="reviewers"
    )
    assert line == "Showing 3 of 1,240 reviewers."


def test_the_filter_branch_never_claims_rows_are_withheld() -> None:
    """The distinction the whole helper turns on: 1,237 rows are
    missing from the table, and none of them is being kept back."""
    line = preview_count_line(
        shown=3, matching=3, total=1240, noun="reviewers"
    )
    assert "more not shown" not in line
    assert "first" not in line


def test_a_filter_matching_nothing_still_reports_the_pool() -> None:
    line = preview_count_line(
        shown=0, matching=0, total=5, noun="observers"
    )
    assert line == "Showing 0 of 5 observers."


# --------------------------------------------------------------------------- #
# Cap branch, unfiltered — the pool is the whole roster.
# --------------------------------------------------------------------------- #


def test_capped_and_unfiltered_names_the_roster_as_the_pool() -> None:
    line = preview_count_line(
        shown=200, matching=1240, total=1240, noun="reviewers"
    )
    assert line == (
        "Showing first 200 of 1,240 reviewers; 1,040 more not shown."
    )


def test_capped_and_unfiltered_omits_the_word_matching() -> None:
    """No filter ran, so calling the pool "matching" would invent a
    narrowing the operator never asked for."""
    line = preview_count_line(
        shown=200, matching=1240, total=1240, noun="reviewers"
    )
    assert "matching" not in line


# --------------------------------------------------------------------------- #
# Cap branch, filtered — the pool is the matching set.
#
# The state no test covered before Item 10: `test_reviewers_page_
# filter.py::test_filtered_cap_lifts_to_500` looks like it does, but
# seeds 600 rows all of which match, so total == matching and the two
# readings of the denominator coincide.
# --------------------------------------------------------------------------- #


def test_capped_and_filtered_counts_against_the_matching_set() -> None:
    line = preview_count_line(
        shown=500, matching=900, total=1240, noun="reviewers"
    )
    assert line == (
        "Showing first 500 of 900 matching reviewers; 400 more not shown."
    )


def test_the_withheld_count_is_drawn_from_the_matching_set() -> None:
    """400, not 740. The 340 rows the filter excluded are not
    withheld — counting them here would overstate what a lifted cap
    would reveal."""
    line = preview_count_line(
        shown=500, matching=900, total=1240, noun="reviewers"
    )
    assert "400 more not shown" in line
    assert "740" not in line


def test_the_word_matching_appears_only_when_a_filter_narrowed() -> None:
    narrowed = preview_count_line(
        shown=500, matching=900, total=1240, noun="reviewers"
    )
    whole = preview_count_line(
        shown=500, matching=1240, total=1240, noun="reviewers"
    )
    assert "matching reviewers" in narrowed
    assert "matching" not in whole


# --------------------------------------------------------------------------- #
# The noun, and formatting.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "noun", ["reviewers", "reviewees", "relationships", "observers"]
)
def test_the_caller_chooses_the_noun(noun: str) -> None:
    line = preview_count_line(
        shown=200, matching=250, total=250, noun=noun
    )
    assert line == (
        f"Showing first 200 of 250 {noun}; 50 more not shown."
    )


def test_every_number_carries_thousands_separators() -> None:
    """Four-figure roster counts are the norm on the pages that can
    hit the cap at all; `1240` reads as a different order of
    magnitude at a glance."""
    line = preview_count_line(
        shown=1000, matching=25000, total=30000, noun="assignments"
    )
    assert line == (
        "Showing first 1,000 of 25,000 matching assignments; "
        "24,000 more not shown."
    )


def test_the_boundary_between_quiet_and_capped_is_one_row() -> None:
    """Off-by-one guard on the branch condition: 200 of 200 is
    quiet, 199 of 200 is the cap branch."""
    assert (
        preview_count_line(
            shown=200, matching=200, total=200, noun="reviewers"
        )
        is None
    )
    assert preview_count_line(
        shown=199, matching=200, total=200, noun="reviewers"
    ) == "Showing first 199 of 200 reviewers; 1 more not shown."


def test_the_boundary_between_quiet_and_filtered_is_one_row() -> None:
    assert (
        preview_count_line(
            shown=200, matching=200, total=200, noun="reviewers"
        )
        is None
    )
    assert preview_count_line(
        shown=199, matching=199, total=200, noun="reviewers"
    ) == "Showing 199 of 200 reviewers."
