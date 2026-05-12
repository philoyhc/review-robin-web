"""Schema-level coverage for Segment 13D PR 5 —
``instruments.sort_display_fields``.

Pins the JSON column contract for Segment 13B's render-path slice
to consume:

- Default state is NULL — every existing instrument carries the
  unset value after the migration (the reviewer surface falls
  back to its current sort policy).
- A small list-of-dicts spec round-trips cleanly through SQLAlchemy
  ``JSON`` on both SQLite and Postgres.

The column sits inert until 13B's render-path slice reads it.
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
    """A fresh instrument carries ``sort_display_fields = NULL``."""

    review_session = _make_session(db, "isdf-default")
    instrument = Instrument(
        session_id=review_session.id, name="Default", order=0
    )
    db.add(instrument)
    db.flush()

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert fetched.sort_display_fields is None


def test_round_trip_sort_spec(db: Session) -> None:
    """A list-of-dicts spec round-trips cleanly through the JSON
    column. Mirrors the shape 13B's render-path slice will read."""

    review_session = _make_session(db, "isdf-rt")
    instrument = Instrument(
        session_id=review_session.id, name="Sorted", order=0
    )
    # Canonical value shape per ``spec/sort_by_reviewee.md`` and
    # the column docstring on ``Instrument.sort_display_fields``.
    # Earlier shape variants (``source_type`` / ``source_field`` /
    # ``direction``) drifted from a prior design pass; 13B PR 1
    # normalised the docstring + this test fixture on the
    # ``display_field_id`` / ``dir`` shape.
    spec = [
        {"display_field_id": 7, "dir": "asc"},
        {"display_field_id": 12, "dir": "desc"},
    ]
    instrument.sort_display_fields = spec
    db.add(instrument)
    db.flush()

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert fetched.sort_display_fields == spec


def test_empty_list_distinct_from_null(db: Session) -> None:
    """The column distinguishes "operator set an empty spec" from
    "operator never set a spec" — empty list != NULL."""

    review_session = _make_session(db, "isdf-empty")
    instrument = Instrument(
        session_id=review_session.id,
        name="EmptySpec",
        order=0,
        sort_display_fields=[],
    )
    db.add(instrument)
    db.flush()

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert fetched.sort_display_fields == []
    assert fetched.sort_display_fields is not None
