from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession, SessionOperator, User


def test_create_redirects_to_detail(client: TestClient, db: Session) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()
    assert response.headers["location"] == f"/operator/sessions/{review_session.id}"


def test_create_inserts_session_operator_row(client: TestClient, db: Session) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()
    user = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    operator = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == user.id,
        )
    ).scalar_one()
    assert operator.role == "owner"


def test_create_writes_session_created_audit_event(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.created")
    ).scalar_one()
    assert event.summary == "Session spring-2026 created"
    assert event.detail is not None
    assert event.detail["session_code"] == "spring-2026"
    assert event.detail["snapshot"]["code"] == "spring-2026"
    assert event.correlation_id is not None
    assert event.actor_user_id is not None


def test_list_shows_users_session(client: TestClient) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert "Spring Reviews" in body
    assert "spring-2026" in body


def test_detail_renders_for_operator(client: TestClient, db: Session) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()

    response = client.get(f"/operator/sessions/{review_session.id}")
    assert response.status_code == 200
    assert "Spring Reviews" in response.text


def test_non_operator_cannot_view_other_session(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    alice_client.post(
        "/operator/sessions",
        data={"name": "Alice's Session", "code": "alice-only"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "alice-only")
    ).scalar_one()

    bob_client = make_client(bob)
    response = bob_client.get(f"/operator/sessions/{review_session.id}")

    assert response.status_code == 403


def test_create_missing_name_returns_422(client: TestClient) -> None:
    response = client.post(
        "/operator/sessions",
        data={"code": "spring-2026"},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_list_empty_state_renders_for_new_user(client: TestClient) -> None:
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert "don't have any sessions yet" in body or "no sessions" in body.lower()
