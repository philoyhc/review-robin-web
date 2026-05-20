"""Schema-level coverage for the Segment 18G Part 0b
session-offset config columns.

Round-trips the four new columns on ``sessions``:

- ``invite_offsets`` — JSON list (consumer: Part 2)
- ``reminder_offsets`` — JSON list (consumer: Part 5)
- ``archive_offset`` — String(16) ISO 8601 duration (consumer: Part 1)
- ``release_until_offset`` — String(16) ISO 8601 duration
  (Participants-platform inert)

All four columns are inert today — no service module reads or
writes them. JSON shape validation lands with the consumer Part.
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


def test_offset_columns_default_to_null(db: Session) -> None:
    review_session = _make_session(db, "offsets-default")

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.invite_offsets is None
    assert reread.reminder_offsets is None
    assert reread.archive_offset is None
    assert reread.release_until_offset is None


def test_invite_offsets_round_trips_list(db: Session) -> None:
    review_session = _make_session(
        db, "invite-offsets", invite_offsets=["-P1D", "-PT2H"]
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.invite_offsets == ["-P1D", "-PT2H"]


def test_reminder_offsets_round_trips_list(db: Session) -> None:
    review_session = _make_session(
        db, "reminder-offsets", reminder_offsets=["-P2D", "-P1D", "-PT4H"]
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.reminder_offsets == ["-P2D", "-P1D", "-PT4H"]


def test_archive_offset_round_trips_duration(db: Session) -> None:
    review_session = _make_session(db, "archive-offset", archive_offset="P30D")

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.archive_offset == "P30D"


def test_release_until_offset_round_trips_duration(db: Session) -> None:
    review_session = _make_session(
        db, "release-until-offset", release_until_offset="P7D"
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.release_until_offset == "P7D"


def test_offset_columns_flip_persists(db: Session) -> None:
    review_session = _make_session(db, "offsets-flip")
    assert review_session.invite_offsets is None
    assert review_session.archive_offset is None

    review_session.invite_offsets = ["-P1D"]
    review_session.reminder_offsets = ["-PT4H"]
    review_session.archive_offset = "P30D"
    review_session.release_until_offset = "P7D"
    db.flush()
    db.expire(review_session)
    assert review_session.invite_offsets == ["-P1D"]
    assert review_session.reminder_offsets == ["-PT4H"]
    assert review_session.archive_offset == "P30D"
    assert review_session.release_until_offset == "P7D"

    review_session.invite_offsets = None
    review_session.reminder_offsets = None
    review_session.archive_offset = None
    review_session.release_until_offset = None
    db.flush()
    db.expire(review_session)
    assert review_session.invite_offsets is None
    assert review_session.reminder_offsets is None
    assert review_session.archive_offset is None
    assert review_session.release_until_offset is None


def test_max_offset_string_fits(db: Session) -> None:
    """The String(16) singletons fit the documented 10-day maximum
    representation (``-PT240H`` = 7 chars) with comfortable headroom.
    """

    review_session = _make_session(
        db, "max-offset", archive_offset="-PT240H", release_until_offset="P10D"
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.archive_offset == "-PT240H"
    assert reread.release_until_offset == "P10D"
