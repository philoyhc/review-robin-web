"""Where the "Showing N of M" hint lives — Segment 19I Item 4.

It sat flush right in the operator-actions strip, roughly 950px from
the table it describes. It now sits at the top-left of the preview-table
card, with the rows it counts.

The move has a cost the spec leans on: the hint is what tells an
operator that select-all took the **rendered window** rather than the
whole match. The selected-count pill absorbs that by carrying its own
denominator — `"3 of 4 selected"`, where 4 is the rendered window — so
the two numbers still meet. The pill's text is set by JS, so it is
verified in a browser rather than here; what this file pins is where
the hint is and, just as importantly, where it is not.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession

PAGES = ("reviewers", "reviewees", "observers", "relationships")


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    r = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    s.relationships_enabled = True
    s.observers_enabled = True
    db.commit()
    return s


def _seed(db: Session, s: ReviewSession, *, n: int) -> None:
    """`n` reviewers, half of them tagged, so a tag search trims the
    list and the hint has something to say."""
    from app.db.models import Observer, Relationship

    reviewers = [
        Reviewer(
            session_id=s.id,
            name=f"R{i}",
            email=f"r{i}@example.edu",
            tag_1="Keep" if i % 2 == 0 else "Drop",
        )
        for i in range(n)
    ]
    reviewees = [
        Reviewee(
            session_id=s.id,
            name=f"E{i}",
            email_or_identifier=f"e{i}@example.edu",
            tag_1="Keep" if i % 2 == 0 else "Drop",
        )
        for i in range(n)
    ]
    db.add_all(reviewers + reviewees)
    db.add_all(
        [
            Observer(
                session_id=s.id,
                email=f"o{i}@example.edu",
                display_name=f"O{i}",
                tag_1="Keep" if i % 2 == 0 else "Drop",
            )
            for i in range(n)
        ]
    )
    db.flush()
    db.add_all(
        [
            Relationship(
                session_id=s.id,
                reviewer_id=reviewers[i].id,
                reviewee_id=reviewees[i].id,
                tag_1="Keep" if i % 2 == 0 else "Drop",
            )
            for i in range(n)
        ]
    )
    db.commit()


def _table_card(body: str, page: str) -> str:
    """The preview-table card, from its opening div to the table."""
    table_at = body.index(f'id="{page}-table"')
    card_at = body.rindex('<div class="card">', 0, table_at)
    return body[card_at:table_at]


def _strip(body: str) -> str:
    """The operator-actions card, up to the end of its filter form."""
    start = body.index('class="card operator-actions-card"')
    return body[start : body.index("</form>", start)]


@pytest.mark.parametrize("page", PAGES)
def test_the_hint_renders_above_the_table_it_describes(
    db: Session, client: TestClient, page: str
) -> None:
    s = _make_session(client, db, code=f"sh-{page}")
    _seed(db, s, n=6)

    body = client.get(f"/operator/sessions/{s.id}/{page}?q=Keep").text

    # Filter branch (3 of 6 match, nothing capped): no "first", no
    # withheld clause — the three excluded rows are not being kept
    # back, they do not match. The noun is the page's own, which is
    # what makes this assertion page-specific rather than shared
    # boilerplate (Segment 19I Item 10).
    assert f"Showing 3 of 6 {page}." in _table_card(body, page)


@pytest.mark.parametrize("page", PAGES)
def test_the_hint_carries_the_shared_class(
    db: Session, client: TestClient, page: str
) -> None:
    """All four pages render the line through the same partial, so
    they cannot drift apart in styling the way Assignments did — it
    used `.form-help`, which sets `--fs-small`, and so rendered a
    size smaller than these four (Segment 19I Item 10)."""
    s = _make_session(client, db, code=f"sh-cls-{page}")
    _seed(db, s, n=6)

    body = client.get(f"/operator/sessions/{s.id}/{page}?q=Keep").text

    card = _table_card(body, page)
    assert '<p class="muted table-showing-hint">' in card
    assert "form-help" not in card


@pytest.mark.parametrize("page", PAGES)
def test_the_hint_has_left_the_operator_actions_strip(
    db: Session, client: TestClient, page: str
) -> None:
    """The half of the move that a test can silently miss — and did,
    in the version of `test_setup_delete_scaffold.py` that named the
    hint among three things and only ever asserted two."""
    s = _make_session(client, db, code=f"sh-gone-{page}")
    _seed(db, s, n=6)

    body = client.get(f"/operator/sessions/{s.id}/{page}?q=Keep").text

    assert "Showing" not in _strip(body)


@pytest.mark.parametrize("page", PAGES)
def test_the_hint_is_absent_when_nothing_is_trimmed(
    db: Session, client: TestClient, page: str
) -> None:
    """Unchanged by the move: an untrimmed list has nothing to say, and
    "Showing 6 of 6" would be noise."""
    s = _make_session(client, db, code=f"sh-none-{page}")
    _seed(db, s, n=6)

    body = client.get(f"/operator/sessions/{s.id}/{page}").text

    assert "Showing" not in _table_card(body, page)
    assert "Showing" not in _strip(body)


@pytest.mark.parametrize("page", PAGES)
def test_the_pill_ships_the_two_number_format(
    db: Session, client: TestClient, page: str
) -> None:
    """The server-rendered placeholder matches the format the JS
    writes, so the two cannot drift into disagreeing about the shape.
    The live text is checked in a browser."""
    s = _make_session(client, db, code=f"sh-pill-{page}")
    _seed(db, s, n=4)

    body = client.get(f"/operator/sessions/{s.id}/{page}").text

    assert f'id="{page}-selected-count" hidden>0 of 0 selected</span>' in body
