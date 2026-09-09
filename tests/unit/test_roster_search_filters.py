"""Per-column search matching on the roster filter predicates.

Segment 19I Item 1. Before it, `filter_reviewers_rows` /
`filter_reviewees_rows` / `filter_observers_rows` matched name and
handle by substring and could not see tag columns at all — and no test
called any of them directly, so their behavior was pinned only through
rendered pages.

The rule these tests exist to hold: **name and handle by substring,
tag columns by whole value, unioned.** It is per column rather than
per input because an input-level rule ("exact if it equals a known
value, else substring") makes one input mean different things on
different rosters — see `test_a_tag_equal_to_a_name_adds_rows`.
"""

from __future__ import annotations

from app.db.models import Observer, Reviewee, Reviewer
from app.web.views import (
    filter_observers_rows,
    filter_reviewees_rows,
    filter_reviewers_rows,
    observers_search_options,
    reviewees_search_options,
    reviewers_search_options,
)


def _reviewer(name: str, email: str, **tags: str) -> Reviewer:
    return Reviewer(session_id=1, name=name, email=email, status="active", **tags)


def _names(rows: list[Reviewer]) -> set[str]:
    return {r.name for r in rows}


# ── The Ethan case ─────────────────────────────────────────────────────


def test_a_partial_name_returns_every_row_carrying_it() -> None:
    rows = [
        _reviewer("Ethan Wong", "ew@example.edu"),
        _reviewer("Ethan Lim", "el@example.edu"),
        _reviewer("Mia Tan", "mt@example.edu"),
    ]

    assert _names(filter_reviewers_rows(rows, status="all", search="Ethan")) == {
        "Ethan Wong",
        "Ethan Lim",
    }


def test_a_tag_equal_to_a_name_adds_rows_rather_than_narrowing() -> None:
    """The case that decided the rule.

    Under an input-level "exact match wins" rule, the presence of a tag
    valued `Ethan` would flip this search into exact mode and return
    only Mia — silently dropping both Ethans. The same input would mean
    different things on two rosters, decided by data the operator
    cannot see.
    """
    rows = [
        _reviewer("Ethan Wong", "ew@example.edu"),
        _reviewer("Ethan Lim", "el@example.edu"),
        _reviewer("Mia Tan", "mt@example.edu", tag_1="Ethan"),
    ]

    assert _names(filter_reviewers_rows(rows, status="all", search="Ethan")) == {
        "Ethan Wong",
        "Ethan Lim",
        "Mia Tan",
    }


# ── Whole-value tags ───────────────────────────────────────────────────


def test_a_tag_search_does_not_bleed_into_a_longer_tag() -> None:
    rows = [
        _reviewer("A", "a@example.edu", tag_1="Team A"),
        _reviewer("B", "b@example.edu", tag_1="Team A2"),
        _reviewer("C", "c@example.edu", tag_1="Team AB"),
    ]

    assert _names(filter_reviewers_rows(rows, status="all", search="Team A")) == {"A"}


def test_a_partial_tag_value_matches_nothing() -> None:
    """`TW2` is not a whole tag value, so the table shows only
    name/handle hits — while the suggestion list still narrows to the
    TW2x values for the operator to pick from. The list explores; the
    filter selects."""
    rows = [_reviewer(f"P{n}", f"p{n}@example.edu", tag_1=f"TW{n:02d}") for n in range(20, 30)]

    assert filter_reviewers_rows(rows, status="all", search="TW2") == []
    assert filter_reviewers_rows(rows, status="all", search="TW23")[0].name == "P23"
    assert "TW23" in reviewers_search_options(rows)


def test_tag_matching_is_case_and_whitespace_insensitive() -> None:
    rows = [_reviewer("A", "a@example.edu", tag_1="  Team A  ")]

    assert filter_reviewers_rows(rows, status="all", search="team a")


def test_an_empty_tag_never_matches() -> None:
    rows = [_reviewer("A", "a@example.edu", tag_1="", tag_2=None)]

    assert filter_reviewers_rows(rows, status="all", search=" ") == rows
    assert filter_reviewers_rows(rows, status="all", search="zzz") == []


# ── The pick path, and the parens it used to swallow ───────────────────


def test_an_offered_label_still_exact_matches_its_handle() -> None:
    rows = [
        _reviewer("Ana Lim", "ana@example.edu"),
        _reviewer("Ana Lim", "ana2@example.edu"),
    ]

    picked = filter_reviewers_rows(
        rows, status="all", search="Ana Lim (ana@example.edu)"
    )

    assert [r.email for r in picked] == ["ana@example.edu"]


def test_a_tag_ending_in_parentheses_matches_its_tag() -> None:
    """The pick path fired on any input ending in `(...)`, so this
    input searched for a handle of `B`. It now fires only on a label
    the page actually offered."""
    rows = [
        _reviewer("A", "a@example.edu", tag_1="Group (B)"),
        _reviewer("B", "b@example.edu"),
    ]

    assert _names(
        filter_reviewers_rows(rows, status="all", search="Group (B)")
    ) == {"A"}


def test_a_reviewee_tag_in_parentheses_matches_its_tag() -> None:
    """Reviewees had no `"@" in tail` guard — a handle may be a bare
    identifier — so this page was the one most exposed."""
    rows = [
        Reviewee(
            session_id=1,
            name="Carol",
            email_or_identifier="anon-1",
            status="active",
            tag_1="Cohort (2026)",
        ),
        Reviewee(
            session_id=1,
            name="Dan",
            email_or_identifier="2026",
            status="active",
        ),
    ]

    kept = filter_reviewees_rows(rows, status="all", search="Cohort (2026)")

    assert [r.name for r in kept] == ["Carol"]


# ── Per-entity shapes ──────────────────────────────────────────────────


def test_observers_search_their_single_tag_slot() -> None:
    rows = [
        Observer(session_id=1, email="o1@example.edu", display_name="Obs One",
                 status="active", tag_1="Panel A"),
        Observer(session_id=1, email="o2@example.edu", display_name="Obs Two",
                 status="active", tag_1="Panel B"),
    ]

    kept = filter_observers_rows(rows, status="all", search="Panel A")

    assert [o.email for o in kept] == ["o1@example.edu"]


def test_status_and_search_still_compose() -> None:
    rows = [
        _reviewer("A", "a@example.edu", tag_1="Team A"),
        _reviewer("B", "b@example.edu", tag_1="Team A"),
    ]
    rows[1].status = "inactive"

    kept = filter_reviewers_rows(rows, status="active", search="Team A")

    assert _names(kept) == {"A"}


# ── Suggestions ────────────────────────────────────────────────────────


def test_tag_suggestions_are_distinct_values_not_one_per_row() -> None:
    rows = [_reviewer(f"P{n}", f"p{n}@example.edu", tag_1="TW01") for n in range(50)]

    options = reviewers_search_options(rows)

    assert options.count("TW01") == 1
    assert options[0] == "TW01", "tag values lead the list"


def test_a_tag_whose_rows_fall_past_the_display_cap_is_still_offered() -> None:
    """The reachability argument, asserted. The suggestion list is built
    from the whole roster, so it can name a partition the operator
    cannot currently see rows for — picking it brings them in."""
    rows = [_reviewer(f"P{n:04d}", f"p{n}@example.edu", tag_1="Bulk") for n in range(600)]
    rows.append(_reviewer("Zed", "zed@example.edu", tag_1="Rare"))

    options = reviewers_search_options(rows)

    assert "Rare" in options
    # ...while that row's label is past the people cap.
    assert "Zed (zed@example.edu)" not in options
    assert len(filter_reviewers_rows(rows, status="all", search="Rare")) == 1


def test_every_page_offers_its_tags_ahead_of_its_people() -> None:
    reviewees = [
        Reviewee(session_id=1, name="Carol", email_or_identifier="c@example.edu",
                 status="active", tag_2="Alpha")
    ]
    observers = [
        Observer(session_id=1, email="o@example.edu", display_name="Obs",
                 status="active", tag_1="Panel")
    ]

    assert reviewees_search_options(reviewees)[0] == "Alpha"
    assert observers_search_options(observers)[0] == "Panel"
