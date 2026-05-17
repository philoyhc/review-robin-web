"""Schema-level coverage for the Segment 13F PR 3 ``session_tags``
table.

Round-trips the new table, pins the ``(session_id, tag)`` uniqueness
constraint, and pins the ``ON DELETE CASCADE`` on session delete. The
table is inert today — no service module reads or writes
``session_tags`` until Segment 18A Part 2 lights it up.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionTag, User


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


def test_session_tag_round_trips(db: Session) -> None:
    """A tag row persists and reads back with an auto-stamped
    ``created_at``."""

    review_session = _make_session(db, "tag-rt")
    tag = SessionTag(session_id=review_session.id, tag="cohort-A")
    db.add(tag)
    db.flush()

    reread = db.execute(
        select(SessionTag).where(SessionTag.id == tag.id)
    ).scalar_one()
    assert reread.session_id == review_session.id
    assert reread.tag == "cohort-A"
    assert reread.created_at is not None


def test_session_tag_unique_per_session(db: Session) -> None:
    """The same tag cannot be added to one session twice."""

    review_session = _make_session(db, "tag-uniq")
    db.add(SessionTag(session_id=review_session.id, tag="pilot"))
    db.flush()

    db.add(SessionTag(session_id=review_session.id, tag="pilot"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_tag_allowed_on_different_sessions(db: Session) -> None:
    """The uniqueness constraint is per-session — two sessions can
    each carry the same tag string."""

    session_a = _make_session(db, "tag-shared-a")
    session_b = _make_session(db, "tag-shared-b")
    db.add(SessionTag(session_id=session_a.id, tag="2026-Q1"))
    db.add(SessionTag(session_id=session_b.id, tag="2026-Q1"))
    db.flush()

    rows = db.execute(
        select(SessionTag).where(SessionTag.tag == "2026-Q1")
    ).scalars().all()
    assert {r.session_id for r in rows} == {session_a.id, session_b.id}


def test_session_tag_cascades_on_session_delete(db: Session) -> None:
    """Deleting a session drops its tag rows (ON DELETE CASCADE)."""

    review_session = _make_session(db, "tag-cascade")
    db.add(SessionTag(session_id=review_session.id, tag="to-be-dropped"))
    db.flush()
    session_id = review_session.id

    db.delete(review_session)
    db.flush()

    remaining = db.execute(
        select(SessionTag).where(SessionTag.session_id == session_id)
    ).scalars().all()
    assert remaining == []
