"""Unit + integration coverage for the Workflow card's Row 3
manual buttons: Release responses, Stop releasing responses,
Archive session.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.schemas.sessions import SessionCreate
from app.services import session_lifecycle as lifecycle
from app.services import sessions


def _draft_session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name=code.title(), code=code)
    )
    return review_session, op


# ── release_responses_now ────────────────────────────────────────────


def test_release_responses_now_stamps_release_at(db: Session) -> None:
    review_session, op = _draft_session(db, "rel-stamp")
    assert review_session.responses_release_at is None
    lifecycle.release_responses_now(
        db, review_session=review_session, user=op
    )
    assert review_session.responses_release_at is not None
    assert lifecycle.is_response_release_window_open(review_session)


def test_release_responses_now_clears_prior_until(db: Session) -> None:
    review_session, op = _draft_session(db, "rel-clear")
    review_session.responses_release_until = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()
    lifecycle.release_responses_now(
        db, review_session=review_session, user=op
    )
    assert review_session.responses_release_until is None


def test_release_responses_now_emits_audit_event(db: Session) -> None:
    review_session, op = _draft_session(db, "rel-audit")
    review_session.responses_release_until = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()
    lifecycle.release_responses_now(
        db, review_session=review_session, user=op
    )
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_released",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    snapshot = event.detail["snapshot"]
    assert snapshot["cleared_until"] is True
    # ISO-formatted UTC timestamp present.
    assert "T" in snapshot["responses_release_at"]


# ── stop_responses_release ───────────────────────────────────────────


def test_stop_responses_release_stamps_until(db: Session) -> None:
    review_session, op = _draft_session(db, "stop-stamp")
    # Open the release window first.
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) - timedelta(hours=1)
    db.commit()
    assert lifecycle.is_response_release_window_open(review_session)
    lifecycle.stop_responses_release(
        db, review_session=review_session, user=op
    )
    assert review_session.responses_release_until is not None
    assert not lifecycle.is_response_release_window_open(review_session)


def test_stop_responses_release_emits_audit_event(db: Session) -> None:
    review_session, op = _draft_session(db, "stop-audit")
    lifecycle.stop_responses_release(
        db, review_session=review_session, user=op
    )
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_release_stopped",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert "T" in event.detail["snapshot"]["responses_release_until"]


# ── Workflow routes ──────────────────────────────────────────────────


def test_workflow_release_responses_route_stamps_and_redirects(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Rel", "code": "rel-route", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rel-route")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/release-responses",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.responses_release_at is not None


def test_workflow_stop_release_route_stamps_and_redirects(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Stop", "code": "stop-route", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "stop-route")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/stop-release",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.responses_release_until is not None


def test_workflow_archive_route_redirects_to_archived_lobby(
    client: TestClient, db: Session
) -> None:
    """The button lands the operator back on the archived-sessions
    index — they should see their just-archived row in context."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Arch", "code": "arch-route", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "arch-route")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/archive",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sessions/archived"
    db.refresh(review_session)
    assert review_session.status == "archived"


def test_workflow_archive_route_works_from_ready_state(
    client: TestClient, db: Session
) -> None:
    """The underlying ``lifecycle.archive_session`` service is
    permissive (accepts any non-archived state) — distinct from
    the bulk-archive route's draft-only filter. Pins that
    permissiveness for defense-in-depth: a deep-link / curl POST
    from ``ready`` still works even though the Workflow card
    only surfaces the Archive button once the session is
    ``expired`` (the close-then-file-away sequence)."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Arch", "code": "arch-from-ready", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "arch-from-ready")
    ).scalar_one()
    review_session.status = "ready"
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/workflow/archive",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.status == "archived"
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.archived",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["changes"]["status"] == ["ready", "archived"]
