"""Schema-level coverage for the Segment 11C PR F audit-log columns.

Round-trips every new ``email_outbox`` column added by migration
``c4f6a8b0d2e5`` and pins the canonical ``status`` / ``kind`` value
sets so any future widening is a deliberate edit rather than a
silent drift.

The new columns sit inert until Segment 14-1 Part A wires the
dispatch helper; this file is the schema gate that lets that work
land without any further Alembic churn.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EmailOutbox, ReviewSession, User
from app.db.models.email_outbox import EMAIL_OUTBOX_KINDS, EMAIL_OUTBOX_STATUSES


def _make_session(db: Session, code: str) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_audit_log_columns_round_trip(db: Session) -> None:
    review_session = _make_session(db, "outbox-rt")
    delivered = datetime(2026, 5, 7, 12, 30, tzinfo=timezone.utc)

    row = EmailOutbox(
        session_id=review_session.id,
        kind="invitation",
        to_email="rae@example.edu",
        subject="Welcome",
        body="hello",
        status="queued",
        error_message="SMTP 451 transient",
        from_address="noreply@example.edu",
        backend="smtp",
        backend_message_id="<abc.123@mail.example.edu>",
        delivered_at=delivered,
        payload_hash="a" * 64,
        correlation_id="invitation:1:42",
    )
    db.add(row)
    db.flush()

    fetched = db.execute(
        select(EmailOutbox).where(EmailOutbox.id == row.id)
    ).scalar_one()

    assert fetched.error_message == "SMTP 451 transient"
    assert fetched.from_address == "noreply@example.edu"
    assert fetched.backend == "smtp"
    assert fetched.backend_message_id == "<abc.123@mail.example.edu>"
    # SQLite drops tzinfo on read; compare instants rather than tz state.
    assert fetched.delivered_at is not None
    assert fetched.delivered_at.replace(tzinfo=timezone.utc) == delivered
    assert fetched.payload_hash == "a" * 64
    assert fetched.correlation_id == "invitation:1:42"


def test_audit_log_columns_default_to_null(db: Session) -> None:
    review_session = _make_session(db, "outbox-null")

    row = EmailOutbox(
        session_id=review_session.id,
        kind="invitation",
        to_email="rae@example.edu",
        subject="Welcome",
        body="hello",
        status="queued",
    )
    db.add(row)
    db.flush()

    fetched = db.execute(
        select(EmailOutbox).where(EmailOutbox.id == row.id)
    ).scalar_one()

    assert fetched.error_message is None
    assert fetched.from_address is None
    assert fetched.backend is None
    assert fetched.backend_message_id is None
    assert fetched.delivered_at is None
    assert fetched.payload_hash is None
    assert fetched.correlation_id is None


def test_correlation_id_lookup(db: Session) -> None:
    """Sanity check the indexed-column lookup the 14-1 dispatch helper
    will rely on for idempotent retry."""
    review_session = _make_session(db, "outbox-corr")

    db.add_all(
        [
            EmailOutbox(
                session_id=review_session.id,
                kind="invitation",
                to_email="a@example.edu",
                subject="s",
                body="b",
                status="queued",
                correlation_id="invitation:1:1",
            ),
            EmailOutbox(
                session_id=review_session.id,
                kind="reminder",
                to_email="b@example.edu",
                subject="s",
                body="b",
                status="queued",
                correlation_id="reminder:1:2:1",
            ),
        ]
    )
    db.flush()

    hit = db.execute(
        select(EmailOutbox).where(EmailOutbox.correlation_id == "reminder:1:2:1")
    ).scalar_one()
    assert hit.kind == "reminder"
    assert hit.to_email == "b@example.edu"


def test_canonical_status_value_set() -> None:
    assert EMAIL_OUTBOX_STATUSES == ("queued", "sending", "sent", "failed")


def test_canonical_kind_value_set() -> None:
    assert EMAIL_OUTBOX_KINDS == ("invitation", "reminder", "responses_received")
