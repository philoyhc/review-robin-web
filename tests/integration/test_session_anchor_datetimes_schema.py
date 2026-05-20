"""Schema-level coverage for the Segment 18G Part 0a
session-anchor datetime columns.

Round-trips the two new ``DateTime(timezone=True)`` columns on
``sessions`` — ``scheduled_activate_at`` (consumer: Part 3) and
``responses_release_at`` (Participants-platform inert). Both
columns are inert today — no service module reads or writes them.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User


def _make_session(db: Session, code: str, **kwargs: object) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id, **kwargs
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_anchor_datetimes_default_to_null(db: Session) -> None:
    review_session = _make_session(db, "anchors-default")

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.scheduled_activate_at is None
    assert reread.responses_release_at is None


def test_scheduled_activate_at_round_trips(db: Session) -> None:
    when = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "scheduled-activate", scheduled_activate_at=when
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.scheduled_activate_at is not None
    assert reread.scheduled_activate_at.replace(tzinfo=timezone.utc) == when


def test_responses_release_at_round_trips(db: Session) -> None:
    when = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "responses-release", responses_release_at=when
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.responses_release_at is not None
    assert reread.responses_release_at.replace(tzinfo=timezone.utc) == when


def test_anchor_datetimes_flip_persists(db: Session) -> None:
    review_session = _make_session(db, "anchors-flip")
    assert review_session.scheduled_activate_at is None

    review_session.scheduled_activate_at = datetime(
        2026, 8, 1, 10, 0, tzinfo=timezone.utc
    )
    review_session.responses_release_at = datetime(
        2026, 8, 31, 10, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.expire(review_session)
    assert review_session.scheduled_activate_at is not None
    assert review_session.responses_release_at is not None

    review_session.scheduled_activate_at = None
    review_session.responses_release_at = None
    db.flush()
    db.expire(review_session)
    assert review_session.scheduled_activate_at is None
    assert review_session.responses_release_at is None
