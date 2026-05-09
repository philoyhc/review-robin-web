"""Schema-level coverage for Segment 13D PR 6 —
``instruments.group_kind``.

Pins the column contract for Segment 13C's render-path slice to
consume:

- Default state is NULL — every existing instrument carries the
  unset value after the migration (regular per-reviewee
  instrument).
- A short string round-trips cleanly. 13C settles the actual
  value-set; this test uses representative sample values.

The column sits inert until 13C PR 1 reads it.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User


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


def test_default_state_is_null(db: Session) -> None:
    """A fresh instrument carries ``group_kind = NULL`` — the
    "regular per-reviewee instrument" sentinel."""

    review_session = _make_session(db, "igk-default")
    instrument = Instrument(
        session_id=review_session.id, name="Default", order=0
    )
    db.add(instrument)
    db.flush()

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert fetched.group_kind is None


def test_round_trip_value(db: Session) -> None:
    """A short string round-trips. 13C settles the actual value-set;
    this test pins the column accepts representative samples."""

    review_session = _make_session(db, "igk-rt")
    for sample in ("by_team", "by_role", "single_group"):
        instrument = Instrument(
            session_id=review_session.id,
            name=f"With {sample}",
            order=0,
            group_kind=sample,
        )
        db.add(instrument)
        db.flush()
        fetched = db.execute(
            select(Instrument).where(Instrument.id == instrument.id)
        ).scalar_one()
        assert fetched.group_kind == sample
