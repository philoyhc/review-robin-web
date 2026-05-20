"""Schema-level coverage for the Segment 18G Part 0c
session-retention columns.

Round-trips the two new columns on ``sessions``:

- ``retention_exception`` (Boolean, nullable) — ``NULL`` and
  ``False`` both mean "no exception"; ``True`` opts the session
  out of any auto-purge (e.g. legal hold).
- ``retention_overrides`` (JSON, nullable) — per-session
  override of the deployment retention env-var defaults, plus
  the per-session ``delete_after_archive`` ISO 8601 duration
  (auto-delete offset anchored on the system-stamped archive
  timestamp).

Both columns are inert today — no service module reads or writes
them. JSON shape validation lands with 18G Part 4.
"""
from __future__ import annotations

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


def test_retention_columns_default_to_null(db: Session) -> None:
    review_session = _make_session(db, "retention-default")

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.retention_exception is None
    assert reread.retention_overrides is None


def test_retention_exception_round_trips_bool(db: Session) -> None:
    review_session = _make_session(
        db, "retention-exception", retention_exception=True
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.retention_exception is True


def test_retention_overrides_round_trips_json(db: Session) -> None:
    """The container round-trips the documented override keys plus
    the ``delete_after_archive`` offset."""

    overrides = {
        "response_days": 180,
        "audit_days": 365,
        "archived_days": 90,
        "delete_after_archive": "P30D",
    }
    review_session = _make_session(
        db, "retention-overrides", retention_overrides=overrides
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.retention_overrides == overrides


def test_retention_columns_flip_persists(db: Session) -> None:
    review_session = _make_session(db, "retention-flip")
    assert review_session.retention_exception is None
    assert review_session.retention_overrides is None

    review_session.retention_exception = True
    review_session.retention_overrides = {"response_days": 60}
    db.flush()
    db.expire(review_session)
    assert review_session.retention_exception is True
    assert review_session.retention_overrides == {"response_days": 60}

    review_session.retention_exception = False
    review_session.retention_overrides = None
    db.flush()
    db.expire(review_session)
    assert review_session.retention_exception is False
    assert review_session.retention_overrides is None
