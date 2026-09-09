"""The Assignments search reads the tag columns — 19I Item 7.

Measured before the fix: name and handle matched by substring and the
`Search by:` select already scoped reviewer / reviewee, but the six
tag columns were invisible — `Team A`, `Cohort 1` and `Team B` all
returned zero rows. That is Item 1's gap on a page Item 1 did not
cover.

**Why a conformance table.** The roster pages filter in Python
through `app/web/views/_filters.py::_matches_row`, which *is* Item
1's rule. This page filters in SQL, because `count_pairs` and the
200-row cap both run in the query, and the author's constraint is
that the count keeps its meaning. So the rule is expressed twice,
and two expressions of one rule drift. `CASES` below runs against
**both** paths, so an edit to either shows up as a disagreement
rather than as a silent divergence between two pages.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import assignments
from app.web.views._filters import _matches_row

from ._assignment_states import seed_session_with_assignment

# The seeded reviewer is `Ana Lim / ana@example.edu`, tagged
# `Team A` (tag_1) and `Cohort 1` (tag_2); tag_3 is unset.
REVIEWER_TEXT = ("Ana Lim", "ana@example.edu")
REVIEWER_TAGS = ("Team A", "Cohort 1", None)

CASES: tuple[tuple[str, bool, str], ...] = (
    ("Ana", True, "name, substring"),
    ("ana", True, "name, case-insensitive"),
    ("Ana Lim", True, "name, whole"),
    ("ana@", True, "handle, substring"),
    ("example.edu", True, "handle, substring mid-value"),
    ("Team A", True, "tag_1, whole value"),
    ("team a", True, "tag, case-insensitive"),
    ("  Team A  ", True, "tag, surrounding whitespace ignored"),
    ("Cohort 1", True, "tag_2, whole value"),
    ("Team", False, "tag, substring must NOT match"),
    ("Team A2", False, "tag, near-miss must NOT match"),
    ("eam A", False, "tag, infix must NOT match"),
    ("zzz", False, "no column matches"),
)


@pytest.mark.parametrize(("term", "expected", "label"), CASES)
def test_the_python_rule(term: str, expected: bool, label: str) -> None:
    """Item 1's rule, as the roster pages run it."""
    assert (
        _matches_row(term, text=REVIEWER_TEXT, tags=REVIEWER_TAGS) is expected
    ), label


@pytest.mark.parametrize(("term", "expected", "label"), CASES)
def test_the_sql_rule_agrees(
    db: Session, client: TestClient, term: str, expected: bool, label: str
) -> None:
    """The same table, through the query the page actually runs."""
    s = seed_session_with_assignment(client, db, code=f"ast-{abs(hash(term)) % 99999}")

    count = assignments.count_pairs(
        db, s.id, search=term, search_by="reviewer"
    )

    assert (count > 0) is expected, (label, term, count)


@pytest.mark.parametrize(("term", "expected", "label"), CASES)
def test_list_and_count_agree(
    db: Session, client: TestClient, term: str, expected: bool, label: str
) -> None:
    """`count_pairs` drives `Showing N of M` and `list_pairs` the rows
    themselves. A term that counts but does not list (or the reverse)
    would render a hint that contradicts the table."""
    s = seed_session_with_assignment(client, db, code=f"asl-{abs(hash(term)) % 99999}")

    count = assignments.count_pairs(db, s.id, search=term, search_by="reviewer")
    rows = assignments.list_pairs(db, s.id, search=term, search_by="reviewer")

    assert count == len(rows), (label, term, count, len(rows))
    assert (count > 0) is expected, (label, term)


def test_search_by_scopes_the_tags_to_their_own_side(
    db: Session, client: TestClient
) -> None:
    """Tags belong to the reviewer and the reviewee individually, so
    the existing `Search by:` select scopes them for free — this is
    what made a separate tag control unnecessary.

    Counts are exact, and asserted against the fixture as measured
    rather than as assumed: it holds **two** pairs, both with `Ana
    Lim` as reviewer (one ordinary, one self-review).
    """
    s = seed_session_with_assignment(client, db, code="ast-scope")

    def n(term: str, by: str) -> int:
        return assignments.count_pairs(db, s.id, search=term, search_by=by)

    # `Cohort 1` is the reviewer's alone — the clean scoping pair.
    assert n("Cohort 1", "reviewer") == 2
    assert n("Cohort 1", "reviewee") == 0
    assert n("Cohort 1", "all") == 2

    # `Team B` is the reviewee's alone — the same proof, other way up.
    assert n("Team B", "reviewer") == 0
    assert n("Team B", "reviewee") == 1
    assert n("Team B", "all") == 1


def test_a_tag_shared_across_the_pair_matches_on_both_sides(
    db: Session, client: TestClient
) -> None:
    """`Team A` is on the reviewer *and* on the self-review row's
    reviewee, who is the same person. Scoping is per side, not per
    person, so it matches under both — the self-review row is the
    case where that distinction is visible.
    """
    s = seed_session_with_assignment(client, db, code="ast-shared")

    assert assignments.count_pairs(db, s.id, search="Team A", search_by="reviewer") == 2
    assert assignments.count_pairs(db, s.id, search="Team A", search_by="reviewee") == 1


def test_the_page_renders_tag_matches(
    db: Session, client: TestClient
) -> None:
    """End to end through the route, which is where the operator meets
    it: the hint counts the tag match rather than reporting nothing.

    `Team B` matches one of the two pairs, so the hint renders — it is
    suppressed when the match is the whole roster.
    """
    s = seed_session_with_assignment(client, db, code="ast-page")

    body = client.get(
        f"/operator/sessions/{s.id}/assignments?q=Team+B&search_by=all"
    ).text

    assert "Showing 1 of 2 assignments." in body


def test_a_blank_term_yields_no_tag_predicates() -> None:
    """A whitespace-only term must add **no** tag predicate.

    Without the guard, `lower(trim(tag)) == ''` is true for a row
    whose tag slot holds an empty string rather than NULL — which CSV
    import can produce — so a stray space would "match" every
    untagged row on its tags.

    Asserted on `_tag_matches` rather than through `count_pairs`,
    because an empty term also makes the *name* predicate
    `ILIKE '%%'`, which matches every row whatever the tags do. At
    that level the guard is invisible, which is exactly why dropping
    it passed the whole file.
    """
    from app.db.models import Reviewer
    from app.services.assignments._coverage import _tag_matches

    columns = (Reviewer.tag_1, Reviewer.tag_2, Reviewer.tag_3)

    for term in ("", "   ", "\t", "\n "):
        assert _tag_matches(term, *columns) == [], repr(term)

    assert len(_tag_matches("Team A", *columns)) == 3


def test_the_placeholder_names_every_column_the_search_reads(
    db: Session, client: TestClient
) -> None:
    """It read `Name or email` while the tag columns were invisible,
    which was honest. Now that they match, the placeholder is the
    only thing on the page that says what the box will search.

    Pinned because copy that nothing asserts drifts silently — the
    lesson `lock_action` taught in Item 6.
    """
    s = seed_session_with_assignment(client, db, code="ast-ph")

    body = client.get(f"/operator/sessions/{s.id}/assignments").text

    assert 'placeholder="Name, email or tag"' in body
    assert 'placeholder="Name or email"' not in body
