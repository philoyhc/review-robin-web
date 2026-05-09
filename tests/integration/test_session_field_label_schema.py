"""Schema-level coverage for Segment 13D PR 1 — ``session_field_labels``.

Pins the table contract for Segment 15A's friendly-label resolver
to consume:

- Round-trip insert + read.
- ``UNIQUE (session_id, source_type, source_field)`` enforced.
- ``ON DELETE CASCADE`` on ``session_id`` reaps the rows when the
  owning session is deleted.

The table sits inert until 15A Slice 1 introduces the resolver;
this file is the schema gate that lets that work land without any
further Alembic churn.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionFieldLabel, User


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


def test_round_trip(db: Session) -> None:
    """Insert + read back; default-state columns are all required."""

    review_session = _make_session(db, "sfl-rt")
    row = SessionFieldLabel(
        session_id=review_session.id,
        source_type="reviewer",
        source_field="tag_1",
        label="Cohort",
    )
    db.add(row)
    db.flush()

    fetched = db.execute(
        select(SessionFieldLabel).where(SessionFieldLabel.id == row.id)
    ).scalar_one()
    assert fetched.session_id == review_session.id
    assert fetched.source_type == "reviewer"
    assert fetched.source_field == "tag_1"
    assert fetched.label == "Cohort"


def test_unique_per_session_source_field(db: Session) -> None:
    """Two rows with the same (session, source_type, source_field) tuple
    violate ``uq_session_field_label``. The second insert raises on
    flush."""

    review_session = _make_session(db, "sfl-uq")
    db.add(
        SessionFieldLabel(
            session_id=review_session.id,
            source_type="reviewee",
            source_field="tag_2",
            label="First label",
        )
    )
    db.flush()

    db.add(
        SessionFieldLabel(
            session_id=review_session.id,
            source_type="reviewee",
            source_field="tag_2",
            label="Conflict",
        )
    )

    with pytest.raises(IntegrityError):
        db.flush()


def test_same_field_different_sessions_ok(db: Session) -> None:
    """The unique constraint is per-session — the same
    (source_type, source_field) tuple can override labels in
    different sessions independently."""

    sess_a = _make_session(db, "sfl-multi-a")
    sess_b = _make_session(db, "sfl-multi-b")
    db.add(
        SessionFieldLabel(
            session_id=sess_a.id,
            source_type="pair_context",
            source_field="1",
            label="Course",
        )
    )
    db.add(
        SessionFieldLabel(
            session_id=sess_b.id,
            source_type="pair_context",
            source_field="1",
            label="Project",
        )
    )
    db.flush()

    rows = db.execute(
        select(SessionFieldLabel)
        .where(SessionFieldLabel.source_field == "1")
        .order_by(SessionFieldLabel.session_id)
    ).scalars().all()
    assert len(rows) == 2
    assert {r.label for r in rows} == {"Course", "Project"}


def test_cascade_on_session_delete(db: Session) -> None:
    """Deleting the owning session reaps every label row attached
    to it via ``ON DELETE CASCADE``."""

    review_session = _make_session(db, "sfl-cascade")
    db.add(
        SessionFieldLabel(
            session_id=review_session.id,
            source_type="reviewer",
            source_field="tag_3",
            label="Department",
        )
    )
    db.flush()
    session_id = review_session.id

    db.delete(review_session)
    db.flush()

    remaining = db.execute(
        select(SessionFieldLabel).where(
            SessionFieldLabel.session_id == session_id
        )
    ).scalars().all()
    assert remaining == []
