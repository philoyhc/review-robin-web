"""The preview-count sentence — Segment 19I Item 10, rewritten for
19J.5.

Item 10 made one sentence out of four, and its tests pinned the
distinction it existed for: a **filter** excluded rows (they do not
match, so "more not shown" would be a lie) while a **cap** withheld
them (the operator needs to know before reading the table as
complete).

19J.5 turned the cap into a page size, which settles that distinction
rather than refining it. Where a pager renders, nothing is withheld
and the sentence says nothing — the strip already states the position.
So the sentence is now **the filter's**, and these tests pin the
narrower contract plus the one branch that is on its way out.
"""
from __future__ import annotations

import inspect

import pytest

from app.web.views import preview_count_line


# --------------------------------------------------------------------------- #
# Unfiltered — the pager's territory.
# --------------------------------------------------------------------------- #


def test_a_paged_view_says_nothing() -> None:
    """The heart of the 19J.5 revision. 200 rows of 1,240 are on screen
    and the other 1,040 are one click away, so a sentence about them
    would be a second voice saying what the ranges already say."""
    assert (
        preview_count_line(
            shown=200, pool=1240, noun="reviewers", is_filtered=False
        )
        is None
    )


def test_an_unfiltered_view_that_fits_says_nothing() -> None:
    """`Showing 6 of 6 reviewers.` is noise. Predates Item 10 (Item 4
    set it) and survives the rewrite untouched."""
    assert (
        preview_count_line(
            shown=6, pool=6, noun="reviewers", is_filtered=False
        )
        is None
    )


def test_the_quiet_case_holds_at_zero_rows() -> None:
    assert (
        preview_count_line(
            shown=0, pool=0, noun="reviewers", is_filtered=False
        )
        is None
    )


# --------------------------------------------------------------------------- #
# Filtered, nothing withheld — the common case.
# --------------------------------------------------------------------------- #


def test_a_filtered_view_reports_what_it_shows() -> None:
    assert (
        preview_count_line(
            shown=37, pool=37, noun="reviewers", is_filtered=True
        )
        == "Showing 37 reviewers."
    )


def test_the_filtered_sentence_carries_no_roster_denominator() -> None:
    """Deliberate loss, recorded in 19J.5's Judgment calls: the
    operator no longer reads how far the filter narrowed off this
    sentence. The roster total is on the page anyway, in the info
    card, and the sentence now has one job."""
    line = preview_count_line(
        shown=3, pool=3, noun="reviewers", is_filtered=True
    )
    assert line == "Showing 3 reviewers."
    assert "1,240" not in line
    assert " of " not in line


def test_the_filter_branch_never_claims_rows_are_withheld() -> None:
    line = preview_count_line(
        shown=3, pool=3, noun="reviewers", is_filtered=True
    )
    assert "more not shown" not in line
    assert "first" not in line


def test_a_filter_matching_nothing_still_speaks() -> None:
    assert (
        preview_count_line(
            shown=0, pool=0, noun="observers", is_filtered=True
        )
        == "Showing 0 observers."
    )


def test_a_filter_that_excludes_nothing_is_still_a_filtered_view() -> None:
    """``is_filtered`` is the route's flag, not ``shown < pool``. A
    filter matching every row ran and excluded nothing, and saying so
    is the honest answer — it also keeps the sentence and the pager
    from disagreeing about which mode the page is in."""
    assert (
        preview_count_line(
            shown=1240, pool=1240, noun="reviewers", is_filtered=True
        )
        == "Showing 1,240 reviewers."
    )


# --------------------------------------------------------------------------- #
# Filtered and capped — the 500 cap, which paging does not lift.
# --------------------------------------------------------------------------- #


def test_a_capped_filtered_view_names_the_matching_pool() -> None:
    assert (
        preview_count_line(
            shown=500, pool=900, noun="reviewers", is_filtered=True
        )
        == "Showing 500 of 900 reviewers, 400 more not shown."
    )


def test_the_withheld_count_is_drawn_from_the_matching_set() -> None:
    """400, not 740. The rows the filter excluded are not withheld;
    counting them would overstate what a lifted cap would reveal."""
    line = preview_count_line(
        shown=500, pool=900, noun="reviewers", is_filtered=True
    )
    assert "400 more not shown" in line
    assert "740" not in line


def test_the_word_matching_is_gone() -> None:
    """It disambiguated two pools. With the roster total gone, ``of
    900`` can only mean the matching set, so it has nothing left to
    disambiguate."""
    line = preview_count_line(
        shown=500, pool=900, noun="reviewers", is_filtered=True
    )
    assert "matching" not in line


def test_the_filtered_boundary_between_quiet_and_capped_is_one_row() -> None:
    assert (
        preview_count_line(
            shown=500, pool=500, noun="reviewers", is_filtered=True
        )
        == "Showing 500 reviewers."
    )
    assert preview_count_line(
        shown=499, pool=500, noun="reviewers", is_filtered=True
    ) == "Showing 499 of 500 reviewers, 1 more not shown."


# --------------------------------------------------------------------------- #
# The branch with a removal date.
# --------------------------------------------------------------------------- #


def test_no_unfiltered_view_ever_speaks() -> None:
    """Rung 2 left a transitional ``paged`` argument so a page whose
    pager was still inert could keep the withheld notice it had earned.
    Rung 4 paged the last page, nothing passed ``paged=False`` any
    more, and the branch was dead by construction — so it went.

    This is what stops it coming back: whatever the numbers, an
    unfiltered view says nothing, because every table that renders this
    sentence can now reach every row it holds."""
    for pool in (0, 1, 200, 10_000):
        assert (
            preview_count_line(
                shown=min(pool, 200),
                pool=pool,
                noun="assignments",
                is_filtered=False,
            )
            is None
        )


def test_the_transitional_argument_is_gone() -> None:
    """Named rather than merely absent, so a reader meeting ``paged``
    in an old plan or commit can tell it was retired on purpose."""
    assert "paged" not in inspect.signature(preview_count_line).parameters


# --------------------------------------------------------------------------- #
# The noun, and formatting.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "noun", ["reviewers", "reviewees", "relationships", "observers"]
)
def test_the_caller_chooses_the_noun(noun: str) -> None:
    assert (
        preview_count_line(shown=37, pool=37, noun=noun, is_filtered=True)
        == f"Showing 37 {noun}."
    )


def test_the_noun_is_the_pages_subject_not_its_row_type() -> None:
    """Invitations is one row per reviewer and says ``reviewers``;
    Responses says ``reviewees``."""
    assert (
        preview_count_line(
            shown=12, pool=12, noun="reviewers", is_filtered=True
        )
        == "Showing 12 reviewers."
    )


def test_every_number_carries_thousands_separators() -> None:
    """Four-figure counts are the norm on the pages that can hit a cap
    at all; `1240` reads as a different order of magnitude at a
    glance."""
    assert preview_count_line(
        shown=1000, pool=25000, noun="assignments", is_filtered=True
    ) == "Showing 1,000 of 25,000 assignments, 24,000 more not shown."


def test_a_pool_smaller_than_shown_does_not_produce_a_negative() -> None:
    """Defensive: the two numbers come from different expressions at
    several call sites, and a negative withheld count would render as
    ``-3 more not shown``."""
    assert (
        preview_count_line(
            shown=10, pool=4, noun="reviewers", is_filtered=True
        )
        == "Showing 10 reviewers."
    )


# --------------------------------------------------------------------------- #
# Noun agreement.
#
# The old sentence put the noun against the pool (`Showing 1 of 2
# reviewers.`) where the plural was always right. 19J.5 puts it against
# the count, and `Showing 1 reviewers.` is the commonest case there is —
# an operator searching for one person.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("plural", "singular"),
    [
        ("reviewers", "reviewer"),
        ("reviewees", "reviewee"),
        ("relationships", "relationship"),
        ("observers", "observer"),
        ("assignments", "assignment"),
    ],
)
def test_a_count_of_one_takes_the_singular(plural: str, singular: str) -> None:
    """All five nouns these pages pass, pinned — so a future noun the
    trailing-`s` rule would mangle fails here rather than reaching an
    operator."""
    assert (
        preview_count_line(shown=1, pool=1, noun=plural, is_filtered=True)
        == f"Showing 1 {singular}."
    )


def test_zero_takes_the_plural() -> None:
    assert (
        preview_count_line(shown=0, pool=0, noun="reviewers", is_filtered=True)
        == "Showing 0 reviewers."
    )


def test_the_withheld_sentence_keeps_the_plural_at_one_shown() -> None:
    """There the noun belongs to the pool, not the count: 900 reviewers
    exist and one is on screen."""
    assert preview_count_line(
        shown=1, pool=900, noun="reviewers", is_filtered=True
    ) == "Showing 1 of 900 reviewers, 899 more not shown."
