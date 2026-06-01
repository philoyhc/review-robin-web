"""Schema-level coverage for the Segment 18G Part 0b
session-offset config columns and the S12 participant-model
release-window swap.

Round-trips the four columns on ``sessions``:

- ``invite_offsets`` — JSON list (consumer: Part 2)
- ``reminder_offsets`` — JSON list (consumer: Part 5)
- ``archive_offset`` — String(16) ISO 8601 duration (consumer: Part 1)
- ``responses_release_until`` — DateTime(tz) absolute close (S12 —
  replaced the W14 ``release_until_offset`` ISO 8601 duration in
  favour of an absolute close datetime so the Edit form and the
  Stop release button can write to the same column).

JSON shape validation lands with each consumer Part.
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


def _naive_utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=None) if value is not None else None


def test_offset_columns_default_to_null(db: Session) -> None:
    review_session = _make_session(db, "offsets-default")

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.invite_offsets is None
    assert reread.reminder_offsets is None
    assert reread.archive_offset is None
    assert reread.responses_release_until is None


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


def test_responses_release_until_round_trips_datetime(db: Session) -> None:
    until = datetime(2027, 5, 1, 12, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "release-until-dt", responses_release_until=until
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert _naive_utc(reread.responses_release_until) == datetime(
        2027, 5, 1, 12, 0
    )


def test_offset_columns_flip_persists(db: Session) -> None:
    review_session = _make_session(db, "offsets-flip")
    assert review_session.invite_offsets is None
    assert review_session.archive_offset is None

    until = datetime(2027, 7, 7, 12, 0, tzinfo=timezone.utc)
    review_session.invite_offsets = ["-P1D"]
    review_session.reminder_offsets = ["-PT4H"]
    review_session.archive_offset = "P30D"
    review_session.responses_release_until = until
    db.flush()
    db.expire(review_session)
    assert review_session.invite_offsets == ["-P1D"]
    assert review_session.reminder_offsets == ["-PT4H"]
    assert review_session.archive_offset == "P30D"
    assert _naive_utc(review_session.responses_release_until) == datetime(
        2027, 7, 7, 12, 0
    )

    review_session.invite_offsets = None
    review_session.reminder_offsets = None
    review_session.archive_offset = None
    review_session.responses_release_until = None
    db.flush()
    db.expire(review_session)
    assert review_session.invite_offsets is None
    assert review_session.reminder_offsets is None
    assert review_session.archive_offset is None
    assert review_session.responses_release_until is None


def test_max_offset_string_fits(db: Session) -> None:
    """The String(16) singletons fit the documented 10-day maximum
    representation (``-PT240H`` = 7 chars) with comfortable headroom.
    """

    review_session = _make_session(
        db, "max-offset", archive_offset="-PT240H"
    )

    reread = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert reread.archive_offset == "-PT240H"
