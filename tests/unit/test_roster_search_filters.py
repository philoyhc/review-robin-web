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

from app.db.models import Observer, Relationship, Reviewee, Reviewer
from app.web.views._invitations import InvitationsRow
from app.web.views._responses import ResponsesRow
from app.web.views import (
    filter_invitations_rows,
    filter_observers_rows,
    filter_reviewees_rows,
    filter_relationships_rows,
    filter_responses_rows,
    filter_reviewers_rows,
    invitations_search_options,
    observers_search_options,
    relationships_search_options,
    responses_search_options,
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


# ── Relationships ──────────────────────────────────────────────────────
#
# Segment 19I Item 1 rewrote this predicate: it used to take a
# ``search_by`` dimension and match one side of the pair. It now takes a
# ``status`` like the other three pages and matches both sides plus the
# row's own pair-context tags, under the same per-column rule.


def _pair(
    rid: int,
    *,
    reviewer: Reviewer,
    reviewee: Reviewee,
    status: str = "active",
    **tags: str,
) -> Relationship:
    return Relationship(
        id=rid,
        session_id=1,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        status=status,
        **tags,
    )


def _rv(pk: int, name: str, email: str) -> Reviewer:
    return Reviewer(id=pk, session_id=1, name=name, email=email, status="active")


def _re(pk: int, name: str, handle: str) -> Reviewee:
    return Reviewee(
        id=pk,
        session_id=1,
        name=name,
        email_or_identifier=handle,
        status="active",
    )


def _maps(
    reviewers: list[Reviewer], reviewees: list[Reviewee]
) -> dict[str, dict[int, object]]:
    return {
        "reviewer_by_id": {r.id: r for r in reviewers},
        "reviewee_by_id": {r.id: r for r in reviewees},
    }


def test_one_needle_reaches_both_sides_of_the_pair() -> None:
    """The 15F predicate needed the operator to say which side to look
    at; a reviewee named like the needle was invisible on the reviewer
    dimension."""
    ali = _rv(1, "Ali Chen", "ali@example.edu")
    bob = _rv(2, "Bob Ray", "bob@example.edu")
    zeta = _re(1, "Zeta Lim", "zeta@example.edu")
    yara = _re(2, "Yara Ng", "yara@example.edu")
    rows = [
        _pair(1, reviewer=ali, reviewee=zeta),
        _pair(2, reviewer=bob, reviewee=yara),
    ]

    kept = filter_relationships_rows(
        rows, status="all", search="Zeta", **_maps([ali, bob], [zeta, yara])
    )

    assert [r.id for r in kept] == [1]


def test_a_pair_context_tag_matches_by_whole_value() -> None:
    ali = _rv(1, "Ali Chen", "ali@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [
        _pair(1, reviewer=ali, reviewee=carol, tag_1="TW01"),
        _pair(2, reviewer=ali, reviewee=carol, tag_1="TW02"),
        _pair(3, reviewer=ali, reviewee=carol, tag_1="TW010"),
    ]
    maps = _maps([ali], [carol])

    assert [r.id for r in filter_relationships_rows(
        rows, status="all", search="TW01", **maps
    )] == [1], "whole value, so TW010 is not a hit"
    assert filter_relationships_rows(
        rows, status="all", search="TW0", **maps
    ) == [], "a prefix matches no tag"


def test_a_pair_context_tag_equal_to_a_name_adds_rows() -> None:
    """The Ethan case at pair level: a tag whose value happens to equal
    a person's name unions with the name matches rather than replacing
    them."""
    ethan = _rv(1, "Ethan Wong", "ew@example.edu")
    mia = _rv(2, "Mia Tan", "mt@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [
        _pair(1, reviewer=ethan, reviewee=carol),
        _pair(2, reviewer=mia, reviewee=carol, tag_1="Ethan"),
    ]

    kept = filter_relationships_rows(
        rows, status="all", search="Ethan", **_maps([ethan, mia], [carol])
    )

    assert {r.id for r in kept} == {1, 2}


def test_status_narrows_before_the_search_runs() -> None:
    ali = _rv(1, "Ali Chen", "ali@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [
        _pair(1, reviewer=ali, reviewee=carol, tag_1="TW01"),
        _pair(2, reviewer=ali, reviewee=carol, tag_1="TW01", status="inactive"),
    ]

    kept = filter_relationships_rows(
        rows, status="active", search="TW01", **_maps([ali], [carol])
    )

    assert [r.id for r in kept] == [1]


def test_a_dangling_side_does_not_crash_or_match() -> None:
    """A row whose reviewer FK is absent from the map still filters —
    the present side is matched and the missing one is skipped."""
    ali = _rv(1, "Ali Chen", "ali@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [_pair(1, reviewer=ali, reviewee=carol)]

    maps = {"reviewer_by_id": {}, "reviewee_by_id": {carol.id: carol}}

    assert filter_relationships_rows(rows, status="all", search="Ali", **maps) == []
    assert [r.id for r in filter_relationships_rows(
        rows, status="all", search="Carol", **maps
    )] == [1]


def test_a_reviewer_and_reviewee_sharing_a_primary_key_both_appear() -> None:
    """Both roster tables start at id 1, so a suggestion map keyed on
    ``person.id`` alone would drop one of them. Keyed per side."""
    ali = _rv(1, "Ali Chen", "ali@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [_pair(1, reviewer=ali, reviewee=carol)]

    options = relationships_search_options(rows, **_maps([ali], [carol]))

    assert "Ali Chen (ali@example.edu)" in options
    assert "Carol Ho (carol@example.edu)" in options


def test_relationship_suggestions_lead_with_pair_context_tags() -> None:
    ali = _rv(1, "Ali Chen", "ali@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [
        _pair(1, reviewer=ali, reviewee=carol, tag_1="Panel A"),
        _pair(2, reviewer=ali, reviewee=carol, tag_1="Panel A", tag_2="Round 2"),
    ]

    options = relationships_search_options(rows, **_maps([ali], [carol]))

    assert options[:2] == ["Panel A", "Round 2"], "distinct tags, sorted, first"
    assert options.count("Ali Chen (ali@example.edu)") == 1


def test_picking_an_offered_label_exact_matches_on_either_side() -> None:
    """Two people whose handles share a prefix: picking the suggestion
    for one must not drag the other in through the substring path."""
    ana = _rv(1, "Ana Lim", "ana@example.edu")
    ana2 = _rv(2, "Ana Lim", "ana2@example.edu")
    carol = _re(1, "Carol Ho", "carol@example.edu")
    rows = [
        _pair(1, reviewer=ana, reviewee=carol),
        _pair(2, reviewer=ana2, reviewee=carol),
    ]

    kept = filter_relationships_rows(
        rows,
        status="all",
        search="Ana Lim (ana@example.edu)",
        **_maps([ana, ana2], [carol]),
    )

    assert [r.id for r in kept] == [1]


# ── Invitations and Responses (Segment 19I Item 11 rung 4) ─────────────
#
# Both pages matched name and handle by substring and could not see the
# tag columns at all — the same gap Item 1 closed on the rosters, on the
# two pages Item 1 did not cover. They now call the same `_matches_row`,
# so `Team A` finds its rows and does not drag in `Team A2`.


def _invitation_row(reviewer: Reviewer) -> InvitationsRow:
    """Only ``reviewer`` matters to the filter; the rest is scaffolding
    the dataclass requires."""
    return InvitationsRow(
        reviewer=reviewer,
        invitation=None,
        email_status="not sent",
        email_sent_at=None,
        review_progress_state="not started",
        review_progress_done=0,
        review_progress_total=1,
        required_fields_done=0,
        required_fields_total=1,
        last_reminder_at=None,
    )


def _reviewee_with_tags(name: str, handle: str, **tags: str) -> Reviewee:
    """`_re` above takes a pk and no tags; this section needs tags."""
    return Reviewee(
        session_id=1,
        name=name,
        email_or_identifier=handle,
        status="active",
        **tags,
    )


def _response_row(reviewee: Reviewee) -> ResponsesRow:
    return ResponsesRow(
        reviewee=reviewee,
        coverage_state="no responses",
        reviewers_done=0,
        reviewers_total=1,
        last_response_at=None,
    )


def test_invitations_search_now_reads_the_tag_columns() -> None:
    """The behaviour rung 4 adds. Before it this returned no rows: a
    tag value is a substring of no name and no email."""
    rows = [
        _invitation_row(_reviewer("Ana", "ana@example.edu", tag_1="Team A")),
        _invitation_row(_reviewer("Ben", "ben@example.edu", tag_1="Team B")),
    ]

    kept = filter_invitations_rows(rows, status="all", search="Team A")

    assert {r.reviewer.name for r in kept} == {"Ana"}


def test_invitations_tags_match_whole_value_not_prefix() -> None:
    """`Team A` must not drag in `Team A2` — the rule Item 1 set, which
    prefix matching would break."""
    rows = [
        _invitation_row(_reviewer("Ana", "ana@example.edu", tag_1="Team A")),
        _invitation_row(_reviewer("Ben", "ben@example.edu", tag_1="Team A2")),
    ]

    kept = filter_invitations_rows(rows, status="all", search="Team A")

    assert {r.reviewer.name for r in kept} == {"Ana"}


def test_invitations_name_and_email_still_match_by_substring() -> None:
    """Tags being whole-value must not have made the text columns
    exact — a partial name is the common case."""
    rows = [
        _invitation_row(_reviewer("Ana Lim", "ana@example.edu", tag_1="Team A")),
        _invitation_row(_reviewer("Ben Ord", "ben@example.edu", tag_1="Team B")),
    ]

    assert {
        r.reviewer.name
        for r in filter_invitations_rows(rows, status="all", search="na L")
    } == {"Ana Lim"}


def test_invitations_search_reads_all_three_tag_slots() -> None:
    rows = [
        _invitation_row(
            _reviewer("Ana", "ana@example.edu", tag_1="T1", tag_2="T2", tag_3="T3")
        ),
        _invitation_row(_reviewer("Ben", "ben@example.edu", tag_1="Other")),
    ]
    for term in ("T1", "T2", "T3"):
        kept = filter_invitations_rows(rows, status="all", search=term)
        assert {r.reviewer.name for r in kept} == {"Ana"}, term


def test_responses_search_now_reads_the_tag_columns() -> None:
    rows = [
        _response_row(_reviewee_with_tags("Carol", "carol@example.edu", tag_1="Group A")),
        _response_row(_reviewee_with_tags("Dave", "dave@example.edu", tag_1="Group B")),
    ]

    kept = filter_responses_rows(rows, status="all", search="Group A")

    assert {r.reviewee.name for r in kept} == {"Carol"}


def test_responses_tags_match_whole_value_not_prefix() -> None:
    rows = [
        _response_row(_reviewee_with_tags("Carol", "carol@example.edu", tag_1="Group A")),
        _response_row(_reviewee_with_tags("Dave", "dave@example.edu", tag_1="Group A2")),
    ]

    kept = filter_responses_rows(rows, status="all", search="Group A")

    assert {r.reviewee.name for r in kept} == {"Carol"}


def test_neither_datalist_offers_tag_values() -> None:
    """Already true before rung 4, and pinned here because rung 4 is
    what makes tags matchable: a tag identifies too many rows to be a
    useful *suggestion*, which is the distinction Item 9 drew on the
    Assignments page. Matching a tag and suggesting one are different
    questions.
    """
    inv = [
        _invitation_row(_reviewer("Ana", "ana@example.edu", tag_1="Team A"))
    ]
    resp = [
        _response_row(_reviewee_with_tags("Carol", "carol@example.edu", tag_1="Group A"))
    ]

    assert invitations_search_options(inv) == ["Ana (ana@example.edu)"]
    assert responses_search_options(resp) == ["Carol (carol@example.edu)"]
