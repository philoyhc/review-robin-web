"""The Assignments search suggests, and a picked suggestion works.

Segment 19I Item 9 PR 2. The four roster pages gained a `<datalist>`
in Item 1; this page had none. And the rule that goes with it is not
polish — measured before this PR, submitting a label as-is returned
**0 rows**, because `%Ana Lim (ana@example.edu)%` is a substring of
no name and no email. Without the picked-label rule, clicking a
suggestion empties the table.

The list carries **name / handle labels only**. Tags are excluded
from the *list* on the author's measurement that a tag identifies too
many rows to partition by here — tag *matching* (Item 7) is
untouched.
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Instrument, Reviewee, Reviewer
from app.services import assignments

from ._assignment_states import seed_session_with_assignment as _seed

PICKED = "Ana Lim (ana@example.edu)"


def _add_lookalike(db: Session, session_id: int) -> None:
    """A second reviewer whose handle has the picked one as a prefix.

    `ana@example.edu` is not a substring of `ana2@example.edu`, but
    `Ana` is a substring of both — so this row is what separates an
    exact handle match from a name match.
    """
    reviewer = Reviewer(
        session_id=session_id, name="Ana Lim", email="ana2@example.edu"
    )
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == session_id)
    ).scalars().first()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalars().first()
    db.add(reviewer)
    db.flush()
    db.add(
        Assignment(
            session_id=session_id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=True,
            created_by_mode="manual",
        )
    )
    db.commit()


def _datalist_options(body: str) -> list[str]:
    m = re.search(
        r'<datalist id="assignments-search-options">(.*?)</datalist>', body, re.S
    )
    if not m:
        return []
    return re.findall(r'<option value="([^"]*)"', m.group(1))


def _showing(body: str) -> str | None:
    m = re.search(r"Showing (\d+) of (\d+)\.", body)
    return m.group(0) if m else None


def test_a_picked_label_returns_that_person_and_not_the_lookalike(
    db: Session, client: TestClient
) -> None:
    """The case the whole rule exists for, through the route — which
    is where the pick is resolved. The service cannot do it alone: it
    does not know which labels the page offered, and that membership
    check is what stops a tag reading as a pick.

    `Ana` matches both reviewers; the picked label must match only the
    one whose handle it names.
    """
    s = _seed(client, db, code="ta-pick")
    _add_lookalike(db, s.id)

    by_name = client.get(
        f"/operator/sessions/{s.id}/assignments?q=Ana&search_by=reviewer"
    ).text
    by_pick = client.get(
        f"/operator/sessions/{s.id}/assignments"
        f"?q=Ana+Lim+%28ana%40example.edu%29&search_by=reviewer"
    ).text

    assert _showing(by_name) is None, "both Anas — all three pairs, so no hint"
    assert _showing(by_pick) == "Showing 2 of 3.", "only the picked handle's pairs"


def test_the_service_matches_a_resolved_handle_by_equality(
    db: Session, client: TestClient
) -> None:
    """The predicate itself, given the handle the route resolves."""
    s = _seed(client, db, code="ta-svc")
    _add_lookalike(db, s.id)

    assert (
        assignments.count_pairs(
            db,
            s.id,
            search=PICKED,
            search_by="reviewer",
            picked_reviewer_handle="ana@example.edu",
        )
        == 2
    )
    # Equality, not prefix: the lookalike is excluded.
    assert (
        assignments.count_pairs(
            db,
            s.id,
            search=PICKED,
            search_by="reviewer",
            picked_reviewer_handle="ana2@example.edu",
        )
        == 1
    )


def test_a_picked_label_scopes_to_the_side(
    db: Session, client: TestClient
) -> None:
    """Ana is reviewer on both pairs and reviewee on the self-review
    row, so the scope separates 'reviews she writes' from 'reviews
    about her' — the reason the `Search by:` select stays."""
    s = _seed(client, db, code="ta-scope")
    picked = "q=Ana+Lim+%28ana%40example.edu%29"

    reviewer = client.get(
        f"/operator/sessions/{s.id}/assignments?{picked}&search_by=reviewer"
    ).text
    reviewee = client.get(
        f"/operator/sessions/{s.id}/assignments?{picked}&search_by=reviewee"
    ).text

    assert _showing(reviewer) is None, "both pairs — she reviews on each"
    assert _showing(reviewee) == "Showing 1 of 2.", "only the self-review row"


def test_an_unpicked_term_still_matches_as_item_7_left_it(
    db: Session, client: TestClient
) -> None:
    """The pick path must not swallow ordinary matching."""
    s = _seed(client, db, code="ta-plain")

    assert assignments.count_pairs(db, s.id, search="Ana", search_by="reviewer") == 2
    assert assignments.count_pairs(db, s.id, search="ana@", search_by="reviewer") == 2
    # Item 7's tag rule, untouched.
    assert assignments.count_pairs(db, s.id, search="Team B", search_by="reviewee") == 1


def test_a_parenthesised_tag_value_is_not_treated_as_a_pick(
    db: Session, client: TestClient
) -> None:
    """`_picked_label_handle` checks membership of the offered labels
    rather than inferring from punctuation, and the tail must contain
    an `@`. A tag like `Group (B)` is neither."""
    s = _seed(client, db, code="ta-tagparen")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == s.id)
    ).scalars().first()
    reviewer.tag_3 = "Group (B)"
    db.commit()

    assert (
        assignments.count_pairs(db, s.id, search="Group (B)", search_by="reviewer")
        == 2
    ), "matched as a whole-value tag, not mistaken for a picked label"


def test_the_datalist_offers_both_sides_and_no_tags(
    db: Session, client: TestClient
) -> None:
    s = _seed(client, db, code="ta-list")

    options = _datalist_options(client.get(
        f"/operator/sessions/{s.id}/assignments"
    ).text)

    assert PICKED in options, "the reviewer's label"
    assert "Ben Ord (ben@example.edu)" in options, "the reviewee's label"
    # Tags match but are deliberately absent from the list.
    assert "Team A" not in options
    assert "Cohort 1" not in options
    assert "Team B" not in options


def test_the_search_input_is_wired_to_the_datalist(
    db: Session, client: TestClient
) -> None:
    s = _seed(client, db, code="ta-wire")

    body = client.get(f"/operator/sessions/{s.id}/assignments").text

    assert 'list="assignments-search-options"' in body
    assert '<datalist id="assignments-search-options">' in body


def test_the_page_renders_the_pick(
    db: Session, client: TestClient
) -> None:
    """End to end, where the operator meets it."""
    s = _seed(client, db, code="ta-page")
    _add_lookalike(db, s.id)

    body = client.get(
        f"/operator/sessions/{s.id}/assignments"
        f"?q=Ana+Lim+%28ana%40example.edu%29&search_by=reviewer"
    ).text

    assert "Showing 2 of 3." in body
