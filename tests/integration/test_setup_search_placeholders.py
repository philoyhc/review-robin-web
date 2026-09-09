"""The roster search boxes' help text names what they actually match.

Segment 19I Item 1 taught the four search boxes to read the tag
columns; their placeholders still said "name or email", which is the
one line of the page telling an operator what to type. The drift is
invisible to every other test — the search worked, the sign over it
was wrong — so it is pinned here.

Asserted against the placeholder of the *search* input specifically,
located by the `list=` that binds it to the page's suggestion
datalist. A bare `"tag" in body` would pass on the tag-column chips,
the tag headers and the friendly-label editor, none of which are this.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed(db: Session, review_session: ReviewSession) -> None:
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    reviewer = Reviewer(
        session_id=review_session.id, name="Ali", email="ali@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.add(
        Observer(
            session_id=review_session.id,
            email="obs@example.edu",
            display_name="Obs",
        )
    )
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.commit()


def _search_input(body: str, *, page: str) -> str:
    """The search `<input>` element, located by the `list=` that binds
    it to that page's suggestion datalist."""
    needle = f'list="{page}-search-options"'
    assert needle in body, f"no search input bound to {page}-search-options"
    start = body.rfind("<input", 0, body.find(needle))
    assert start != -1
    return body[start : body.index(">", body.find(needle)) + 1]


@pytest.mark.parametrize(
    "route, page",
    [
        ("reviewers", "reviewers"),
        ("reviewees", "reviewees"),
        ("observers", "observers"),
        ("relationships", "relationships"),
    ],
)
def test_search_placeholder_names_the_tag_columns(
    db: Session, client: TestClient, route: str, page: str
) -> None:
    review_session = _make_session(client, db, code=f"ph-{route}")
    _seed(db, review_session)

    body = client.get(
        f"/operator/sessions/{review_session.id}/{route}"
    ).text
    element = _search_input(body, page=page)

    assert "placeholder=" in element, element
    placeholder = element.split('placeholder="', 1)[1].split('"', 1)[0]
    assert "tag" in placeholder.casefold(), (
        f"{route} search placeholder does not mention tags: {placeholder!r}"
    )
    # Still names the people columns it has always matched.
    assert "name" in placeholder.casefold()
    assert "email" in placeholder.casefold()


def test_the_relationships_edit_pickers_keep_their_own_help_text(
    db: Session, client: TestClient
) -> None:
    """The Edit / Add row's reviewer and reviewee pickers are a
    different contract — they resolve one person, and they do not
    search tags — so they keep "Search name or email"."""
    review_session = _make_session(client, db, code="ph-pickers")
    _seed(db, review_session)

    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?add=1"
    ).text

    assert 'placeholder="Search name or email"' in body
