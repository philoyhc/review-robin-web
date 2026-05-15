"""Schema-level coverage for the Segment 13F PR 6
``sessions.display_timezone`` column.

Round-trips the new column. The column is inert today — no
service module reads ``display_timezone``.

The column sits inert until Segment 18B PR 3 lights it up
(per-session timezone card + create-time stamping). ``NULL``
means "inherit the creating operator's default timezone".
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


def test_display_timezone_defaults_to_null(db: Session) -> None:
    """A fresh session carries ``display_timezone = NULL`` — the
    "inherit the operator default" sentinel."""

    review_session = _make_session(db, "dtz-default")

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.display_timezone is None


def test_display_timezone_round_trips_iana_name(db: Session) -> None:
    """The column round-trips an IANA zone name string."""

    review_session = _make_session(
        db, "dtz-rt", display_timezone="Asia/Singapore"
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.display_timezone == "Asia/Singapore"


def test_display_timezone_flip_persists(db: Session) -> None:
    """Setting and clearing the override both persist."""

    review_session = _make_session(db, "dtz-flip")
    assert review_session.display_timezone is None

    review_session.display_timezone = "America/New_York"
    db.flush()
    db.expire(review_session)
    assert review_session.display_timezone == "America/New_York"

    review_session.display_timezone = None
    db.flush()
    db.expire(review_session)
    assert review_session.display_timezone is None
