"""Coverage for the Segment 18A Part 3 archiving transitions —
``session_lifecycle.archive_session`` / ``unarchive_session``."""
from __future__ import annotations

import pytest
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


def test_archive_session_flips_draft_to_archived(db: Session) -> None:
    review_session, op = _draft_session(db, "arch-1")

    lifecycle.archive_session(db, review_session=review_session, user=op)

    assert review_session.status == "archived"
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.archived",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["changes"]["status"] == ["draft", "archived"]


def test_archive_session_accepts_non_draft_states(db: Session) -> None:
    """Post-2026-06-02 widening — the workflow card's per-
    session Archive button fires from any non-archived state.
    The audit event records the actual from-state."""
    review_session, op = _draft_session(db, "arch-ready")
    review_session.status = "ready"
    db.commit()

    lifecycle.archive_session(db, review_session=review_session, user=op)
    assert review_session.status == "archived"
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.archived",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["changes"]["status"] == ["ready", "archived"]


def test_archive_session_rejects_already_archived(db: Session) -> None:
    review_session, op = _draft_session(db, "arch-double")
    lifecycle.archive_session(db, review_session=review_session, user=op)

    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.archive_session(
            db, review_session=review_session, user=op
        )


def test_unarchive_session_flips_archived_to_draft(db: Session) -> None:
    review_session, op = _draft_session(db, "unarch-1")
    lifecycle.archive_session(db, review_session=review_session, user=op)

    lifecycle.unarchive_session(db, review_session=review_session, user=op)

    assert review_session.status == "draft"
    assert db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.unarchived",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one() is not None


def test_unarchive_session_rejects_non_archived(db: Session) -> None:
    review_session, op = _draft_session(db, "unarch-draft")

    with pytest.raises(lifecycle.LifecycleError):
        lifecycle.unarchive_session(
            db, review_session=review_session, user=op
        )
