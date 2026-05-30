"""Unit tests for the ``DataShape`` model — pins the
``data_shapes`` table's contract (unique-name-per-session +
CASCADE FKs on every side) before the service / route slices
build on top.

See ``spec/extract_data.md`` "Wiring decisions (resolved
2026-05-29)" for the full contract this table backs.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    DataShape,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)


_INLINE_NUMERIC = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "100int",
    "_inline_min": 0.0,
    "_inline_max": 100.0,
    "_inline_step": 1.0,
}


def _session(db: Session, *, code: str = "ds") -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="DS",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(db: Session, review_session: ReviewSession) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id, name="Form", short_label="F"
    )
    db.add(instrument)
    db.flush()
    return instrument


def _field(
    db: Session, instrument: Instrument
) -> InstrumentResponseField:
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="score",
        label="Score",
        order=0,
        **_INLINE_NUMERIC,
    )
    db.add(field)
    db.flush()
    return field


def _shape(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    instrument: Instrument | None = None,
    field: InstrumentResponseField | None = None,
) -> DataShape:
    shape = DataShape(
        session_id=review_session.id,
        name=name,
        axis="reviewer",
        instrument_id=instrument.id if instrument else None,
        response_field_id=field.id if field else None,
        column_chip_slots=json.dumps(
            ["reviewer:name", "reviewer:email", "reviewer:assigned"]
        ),
    )
    db.add(shape)
    db.flush()
    return shape


def test_unique_constraint_blocks_duplicate_name_per_session(
    db: Session,
) -> None:
    review_session = _session(db, code="dup")
    _shape(db, review_session, name="My shape")
    with pytest.raises(IntegrityError):
        _shape(db, review_session, name="My shape")


def test_same_name_ok_across_sessions(db: Session) -> None:
    """The uniqueness is scoped to the session — two
    different sessions can each have a shape called
    ``My shape``."""
    session_a = _session(db, code="sess-a")
    session_b = _session(db, code="sess-b")
    _shape(db, session_a, name="My shape")
    _shape(db, session_b, name="My shape")  # no error


def test_session_delete_cascades_shapes(db: Session) -> None:
    review_session = _session(db, code="del-sess")
    _shape(db, review_session, name="A")
    _shape(db, review_session, name="B")
    db.delete(review_session)
    db.commit()
    remaining = db.query(DataShape).all()
    assert remaining == []


def test_instrument_delete_cascades_shapes_scoped_to_it(
    db: Session,
) -> None:
    """A shape with a non-null ``instrument_id`` is wiped
    when its anchor instrument disappears. Other shapes on
    the same session that aren't scoped to that instrument
    survive."""
    review_session = _session(db, code="del-instr")
    instrument = _instrument(db, review_session)
    _shape(db, review_session, name="anchored", instrument=instrument)
    _shape(db, review_session, name="loose")
    db.delete(instrument)
    db.commit()
    surviving = {s.name for s in db.query(DataShape).all()}
    assert surviving == {"loose"}


def test_response_field_delete_cascades_anchored_shape(
    db: Session,
) -> None:
    review_session = _session(db, code="del-field")
    instrument = _instrument(db, review_session)
    field = _field(db, instrument)
    _shape(
        db,
        review_session,
        name="field-anchored",
        instrument=instrument,
        field=field,
    )
    db.delete(field)
    db.commit()
    assert db.query(DataShape).all() == []
