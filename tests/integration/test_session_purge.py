"""Segment 18C — the operator-triggered "Purge and archive" action
on the Sessions-lobby expander (`/operator/sessions/archive-selected`
with `purge` values)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _count(db: Session, model, session_id: int) -> int:
    return db.execute(
        select(func.count()).select_from(model).where(
            model.session_id == session_id
        )
    ).scalar_one()


def _draft_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _draft_session_with_rosters(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    review_session = _draft_session(client, db, code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={"file": (
            "r.csv", b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
            "text/csv",
        )},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={"file": (
            "e.csv", b"RevieweeName,RevieweeEmail\nE,e@example.edu\n",
            "text/csv",
        )},
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    db.refresh(review_session)
    return review_session


def test_purge_audit_log_and_archive(
    client: TestClient, db: Session
) -> None:
    """purge=audit_log wipes the pre-existing audit rows; afterwards
    only the purge + archive events the action itself wrote remain."""
    review_session = _draft_session(client, db, "purge-audit")
    assert _count(db, AuditEvent, review_session.id) > 0

    response = client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [review_session.id], "purge": ["audit_log"]},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    assert db.get(ReviewSession, review_session.id).status == "archived"
    events = db.execute(
        select(AuditEvent.event_type).where(
            AuditEvent.session_id == review_session.id
        )
    ).scalars().all()
    assert sorted(events) == ["session.archived", "session.audit_log_purged"]


def test_purge_rosters_and_archive(
    client: TestClient, db: Session
) -> None:
    """purge=rosters clears reviewers / reviewees / assignments;
    instruments retain."""
    review_session = _draft_session_with_rosters(client, db, "purge-rost")
    assert _count(db, Reviewer, review_session.id) == 1
    assert _count(db, Assignment, review_session.id) >= 1
    instruments_before = _count(db, Instrument, review_session.id)

    response = client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [review_session.id], "purge": ["rosters"]},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    assert db.get(ReviewSession, review_session.id).status == "archived"
    assert _count(db, Reviewer, review_session.id) == 0
    assert _count(db, Reviewee, review_session.id) == 0
    assert _count(db, Assignment, review_session.id) == 0
    assert _count(db, Instrument, review_session.id) == instruments_before


def test_purge_responses_and_archive(
    client: TestClient, db: Session
) -> None:
    """purge=responses clears invitation rows; rosters / assignments
    retain."""
    review_session = _draft_session_with_rosters(client, db, "purge-resp")
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    db.add(Invitation(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        token_hash="purge-resp-token-hash",
    ))
    db.commit()
    assert _count(db, Invitation, review_session.id) == 1

    response = client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [review_session.id], "purge": ["responses"]},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    assert db.get(ReviewSession, review_session.id).status == "archived"
    assert _count(db, Invitation, review_session.id) == 0
    assert _count(db, Assignment, review_session.id) >= 1
    assert _count(db, Reviewer, review_session.id) == 1
