from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
)


def _make_session(
    client: TestClient, db: Session, code: str = "edit-test"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": "old"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_with_assignments(client: TestClient, db: Session, code: str) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": "true"},
        follow_redirects=False,
    )
    return review_session


def test_session_edit_persists_and_audits_changes(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)

    response = client.post(
        f"/operator/sessions/{review_session.id}/edit",
        data={
            "name": "Spring v2",
            "code": "edit-test",
            "description": "new description",
            "help_contact": "Prof X <x@example.edu>",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.name == "Spring v2"
    assert review_session.description == "new description"
    assert review_session.help_contact == "Prof X <x@example.edu>"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.updated")
    ).scalar_one()
    changes = event.detail["changes"]
    assert changes["name"] == ["Spring", "Spring v2"]
    assert changes["description"] == ["old", "new description"]
    assert changes["help_contact"] == [None, "Prof X <x@example.edu>"]
    assert "code" not in changes


def test_session_delete_removes_session_and_all_dependents(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_with_assignments(client, db, code="kill-me")
    sid = review_session.id

    response = client.post(
        f"/operator/sessions/{sid}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sessions"

    assert (
        db.execute(select(ReviewSession).where(ReviewSession.id == sid)).first() is None
    )
    assert (
        db.execute(select(Reviewer).where(Reviewer.session_id == sid)).first() is None
    )
    assert (
        db.execute(select(Reviewee).where(Reviewee.session_id == sid)).first() is None
    )
    assert (
        db.execute(select(Assignment).where(Assignment.session_id == sid)).first()
        is None
    )
    assert (
        db.execute(
            select(SessionOperator).where(SessionOperator.session_id == sid)
        ).first()
        is None
    )

    deletion_event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.deleted")
    ).scalar_one()
    assert deletion_event.session_id is None
    assert deletion_event.detail == {
        "snapshot": {"id": sid, "code": "kill-me", "name": "Spring"},
    }

    older_events = db.execute(
        select(AuditEvent).where(AuditEvent.session_id == sid)
    ).all()
    assert older_events == []


def test_session_delete_without_confirm_returns_400(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="no-confirm")

    response = client.post(
        f"/operator/sessions/{review_session.id}/delete",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert (
        db.execute(
            select(ReviewSession).where(ReviewSession.id == review_session.id)
        ).first()
        is not None
    )


def test_delete_all_reviewers_cascades_assignments(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_with_assignments(client, db, code="r-del")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).first()
        is None
    )
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is None
    )

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewers.deleted_all")
    ).scalar_one()
    assert event.detail["counts"] == {"deleted": 1, "cascaded_assignments": 1}


def test_delete_all_reviewees_cascades_assignments(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_with_assignments(client, db, code="e-del")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).first()
        is None
    )
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is None
    )

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewees.deleted_all")
    ).scalar_one()
    assert event.detail["counts"] == {"deleted": 1, "cascaded_assignments": 1}


def test_delete_all_assignments_clears_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_with_assignments(client, db, code="a-del")
    db.refresh(review_session)
    assert review_session.assignment_mode == "full_matrix"

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is None
    )
    db.refresh(review_session)
    assert review_session.assignment_mode is None

    # Reviewer + reviewee still there
    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).first()
        is not None
    )
    assert (
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).first()
        is not None
    )

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "assignments.deleted_all")
    ).scalar_one()
    assert event.detail["counts"] == {"deleted": 1}


def test_non_operator_gets_403_on_destructive_routes(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-only")

    bob_client = make_client(bob)

    edit = bob_client.post(
        f"/operator/sessions/{review_session.id}/edit",
        data={"name": "x", "code": "y"},
        follow_redirects=False,
    )
    assert edit.status_code == 403

    delete = bob_client.post(
        f"/operator/sessions/{review_session.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert delete.status_code == 403

    for path in (
        f"/operator/sessions/{review_session.id}/reviewers/delete-all",
        f"/operator/sessions/{review_session.id}/reviewees/delete-all",
        f"/operator/sessions/{review_session.id}/assignments/delete-all",
    ):
        r = bob_client.post(path, data={"confirm": "true"}, follow_redirects=False)
        assert r.status_code == 403, path
