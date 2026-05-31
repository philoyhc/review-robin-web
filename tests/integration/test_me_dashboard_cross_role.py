"""Coverage for the ``/me`` dashboard's cross-role union — the
page lists every session the signed-in user touches in any
participant role (reviewer / reviewee / observer) and renders
all matching role pills.

Pins the regression where reviewee / observer matches didn't
surface on ``/me`` because the route queried reviewers only.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)


def _make_session_and_activate(
    client: TestClient,
    db: Session,
    *,
    code: str,
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


def _alice(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


def test_me_shows_reviewer_pill_when_user_is_reviewer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-rv")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewer"' in body
    assert "Reviewer" in body


def test_me_shows_reviewee_pill_when_user_only_reviewee(
    client: TestClient, db: Session
) -> None:
    """Reviewee-only row used to be missing entirely because the
    route queried reviewers only. Now it surfaces with a
    Reviewee pill, no reviewer-status pill, and the Session
    name as plain text."""
    review_session = _make_session_and_activate(client, db, code="me-re")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewee"' in body
    assert "Reviewee" in body
    # No reviewer-status pills on a reviewee-only row.
    assert "submitted" not in body
    assert "in progress" not in body


def test_me_shows_observer_pill_when_user_only_observer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-ob")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-observer"' in body
    assert "Observer" in body


def test_me_unions_all_three_roles_on_one_row(
    client: TestClient, db: Session
) -> None:
    """A session where the user holds all three roles renders one
    row carrying all three pills."""
    review_session = _make_session_and_activate(client, db, code="me-all")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
        ]
    )
    db.commit()
    body = client.get("/me").text
    assert body.count('class="pill pill-role-reviewer"') == 1
    assert body.count('class="pill pill-role-reviewee"') == 1
    assert body.count('class="pill pill-role-observer"') == 1


def test_me_matches_case_insensitively(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-case")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="ALICE@EXAMPLE.EDU",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewee"' in body


def test_me_skips_inactive_roster_rows(
    client: TestClient, db: Session
) -> None:
    """Soft-removed roster rows (``status=inactive``) don't put
    the user back on the dashboard — matches the existing
    reviewer behaviour and reflects that inactivation is the
    operator's soft-remove."""
    review_session = _make_session_and_activate(client, db, code="me-inact")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
            status="inactive",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-observer"' not in body


def test_me_skips_other_users_roster_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-other")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    # No role pills should render — alice is in no roster.
    assert 'class="pill pill-role-reviewer"' not in body
    assert 'class="pill pill-role-reviewee"' not in body
    assert 'class="pill pill-role-observer"' not in body
