"""A Settings CSV that repeats a unique key fails the parse phase.

Two data shapes with one name, or two response fields with one
``field_key`` in an instrument, would reach ``uq_data_shape_session_name``
or ``uq_instrument_field_key`` in phase 2 as an ``IntegrityError``, which
the upload routes answered with a 500 (findings 2026-10-03 D1). They are
now named row errors in ``ApplyResult.errors``, and phase 2 never runs.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DataShape,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="DS", code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(
    db: Session, review_session: ReviewSession, *, name: str, short_label: str
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id, name=name, short_label=short_label
    )
    db.add(instrument)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instrument.id,
            field_key="score",
            label="Score",
            order=0,
            _inline_data_type="Integer",
            _inline_response_type="100int",
        )
    )
    db.flush()
    return instrument


def _copied(rows: list[Row], prefix: str, new_prefix: str) -> list[Row]:
    """Every row under ``prefix``, repeated under ``new_prefix``."""
    return [
        row._replace(field=new_prefix + row.field[len(prefix):])
        for row in rows
        if row.field.startswith(prefix)
    ]


def _exported(db: Session) -> list[Row]:
    """One instrument with a ``score`` field and one data shape."""
    source = _session(db, code="dup-src")
    _instrument(db, source, name="Peer review", short_label="Peer")
    db.add(
        DataShape(
            session_id=source.id,
            name="Whole roster",
            axis="reviewer",
            column_chip_slots="[]",
            self_review_handling="include_self",
        )
    )
    db.flush()
    return serialize_session_config(db, source)


def _nothing_written(db: Session, session_id: int) -> bool:
    return not db.execute(
        select(Instrument.id).where(Instrument.session_id == session_id)
    ).first() and not db.execute(
        select(DataShape.id).where(DataShape.session_id == session_id)
    ).first()


def test_a_repeated_data_shape_name_is_a_row_error(db: Session) -> None:
    rows = _exported(db)
    rows += _copied(rows, "data_shapes[0].", "data_shapes[1].")
    destination = _session(db, code="dup-shape")

    result = apply_session_config(db, destination, rows)

    assert not result.ok
    assert [(e.field, e.message) for e in result.errors] == [
        (
            "data_shapes[1].name",
            "duplicate data_shapes name 'Whole roster' (also at data_shapes[0])",
        )
    ]
    assert _nothing_written(db, destination.id)


def test_a_shape_phase_2_skips_does_not_count_as_a_repeat(
    db: Session,
) -> None:
    """Shapes with an unknown axis or no name are skipped on apply, so a
    second one sharing the written shape's name, or two nameless ones,
    are not errors."""
    rows = _exported(db)
    copy = _copied(rows, "data_shapes[0].", "data_shapes[1].")
    rows += [
        row._replace(value="nowhere") if row.field.endswith(".axis") else row
        for row in copy
    ]
    for index in (2, 3):
        rows += [
            row._replace(value="") if row.field.endswith(".name") else row
            for row in _copied(rows, "data_shapes[0].", f"data_shapes[{index}].")
        ]
    destination = _session(db, code="dup-skip")

    result = apply_session_config(db, destination, rows)

    assert result.ok, result.errors
    assert result.counts["data_shapes"] == 1


def test_a_repeated_field_key_in_one_instrument_is_a_row_error(
    db: Session,
) -> None:
    rows = _exported(db)
    rows += _copied(
        rows,
        "instruments[1].response_fields[1].",
        "instruments[1].response_fields[2].",
    )
    destination = _session(db, code="dup-field")

    result = apply_session_config(db, destination, rows)

    assert not result.ok
    assert [(e.field, e.message) for e in result.errors] == [
        (
            "instruments[1].response_fields[2].field_key",
            "duplicate field_key 'score' "
            "(also at instruments[1].response_fields[1])",
        )
    ]
    assert _nothing_written(db, destination.id)


def test_one_field_key_in_two_instruments_is_not_a_repeat(
    db: Session,
) -> None:
    """``field_key`` is unique within an instrument, not across them."""
    source = _session(db, code="dup-two")
    _instrument(db, source, name="Peer review", short_label="Peer")
    _instrument(db, source, name="Self review", short_label="Self")
    rows = serialize_session_config(db, source)
    destination = _session(db, code="dup-two-dst")

    result = apply_session_config(db, destination, rows)

    assert result.ok, result.errors
    assert result.counts["response_fields"] == 2


def test_a_value_longer_than_its_column_is_a_row_error(db: Session) -> None:
    """D32: a data-shape name or ``field_key`` over 255 characters
    passed phase 1 and failed phase 2 on Postgres as a ``DataError`` (a
    500; SQLite stores it). Every string the import writes is now
    checked against its column's declared length in phase 1."""
    rows = _exported(db)
    long_name, long_key = "n" * 256, "k" * 256
    rows = [
        row._replace(value=long_name)
        if row.field == "data_shapes[0].name"
        else row._replace(value=long_key)
        if row.field.endswith(".response_fields[1].field_key")
        else row._replace(value="s" * 33)
        if row.field.endswith("].short_label")
        else row
        for row in rows
    ]
    destination = _session(db, code="too-long")

    result = apply_session_config(db, destination, rows)

    assert not result.ok
    messages = {e.field: e.message for e in result.errors}
    assert messages["data_shapes[0].name"] == "256 characters; at most 255 fit"
    assert messages["instruments[1].response_fields[1].field_key"] == (
        "256 characters; at most 255 fit"
    )
    assert messages["instruments[1].short_label"] == (
        "33 characters; at most 32 fit"
    )
    assert _nothing_written(db, destination.id)

    # At the limit is fine.
    rows = [
        row._replace(value="n" * 255) if row.field == "data_shapes[0].name"
        else row
        for row in _exported_again(db)
    ]
    result = apply_session_config(db, _session(db, code="at-limit"), rows)
    assert result.ok, result.errors


def _exported_again(db: Session) -> list[Row]:
    source = db.scalars(
        select(ReviewSession).where(ReviewSession.code == "dup-src")
    ).one()
    return serialize_session_config(db, source)
