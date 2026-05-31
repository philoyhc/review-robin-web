"""Coverage for the sessions-lobby "My roles" column — matches the
current user's email against the reviewers / reviewees /
observers rosters of every listed session and renders the
corresponding role pills.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession


def _make_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_lobby_shows_roles_column(
    client: TestClient, db: Session
) -> None:
    # The lobby renders an empty-state card when there are no
    # sessions; one row is enough to reveal the table headers.
    _make_session(client, db, "header-probe")
    body = client.get("/operator/sessions").text
    assert 'data-sort-key="roles"' in body
    assert "My roles" in body


def test_lobby_roles_dash_when_user_not_in_any_roster(
    client: TestClient, db: Session
) -> None:
    _make_session(client, db, "no-roles")
    body = client.get("/operator/sessions").text
    # The Roles td renders a muted dash when the user is in
    # none of the rosters. The session row is the only data row.
    assert 'data-sort-value=""' in body


def test_lobby_roles_reviewer_pill_when_user_in_reviewer_roster(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "as-reviewer")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/operator/sessions").text
    assert 'data-sort-value="Reviewer"' in body
    assert ">Reviewer<" in body


def test_lobby_roles_reviewee_pill_matches_case_insensitive(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "as-reviewee")
    # Email stored in different case than the auth identity.
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="Alice@Example.EDU",
        )
    )
    db.commit()
    body = client.get("/operator/sessions").text
    assert ">Reviewee<" in body


def test_lobby_roles_observer_pill_when_user_in_observer_roster(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "as-observer")
    review_session.observers_enabled = True
    db.commit()
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    body = client.get("/operator/sessions").text
    assert ">Observer<" in body


def test_lobby_roles_multiple_pills_in_canonical_order(
    client: TestClient, db: Session
) -> None:
    """When the user holds multiple roles, pills render
    Reviewer → Reviewee → Observer regardless of insertion order."""
    review_session = _make_session(client, db, "all-roles")
    review_session.observers_enabled = True
    db.commit()
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
        ]
    )
    db.commit()
    body = client.get("/operator/sessions").text
    # All three labels appear in the row's sort value, in canonical
    # order.
    assert 'data-sort-value="Reviewer Reviewee Observer"' in body


def test_lobby_roles_isolated_per_session(
    client: TestClient, db: Session
) -> None:
    """A reviewer match in session A doesn't bleed into the row
    for session B."""
    s_match = _make_session(client, db, "match")
    _make_session(client, db, "other")
    db.add(
        Reviewer(
            session_id=s_match.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/operator/sessions").text
    assert 'data-sort-value="Reviewer"' in body
    # The non-match row carries an empty data-sort-value.
    assert 'data-sort-value=""' in body
