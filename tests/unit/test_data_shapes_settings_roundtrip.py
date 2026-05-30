"""Settings CSV round-trip for saved Data shapes (PR 6 of
the Data shaper wiring slice).

Exports a session with saved shapes via
``serialize_session_config`` and applies the row list back
to a fresh session via ``apply_session_config`` — asserts
the shapes round-trip with their portable references
(instrument by short_label, response field by field_key)
resolving to the new session's FKs.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DataShape,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services import session_config_io


_INLINE_NUMERIC = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "100int",
    "_inline_min": 1.0,
    "_inline_max": 5.0,
    "_inline_step": 1.0,
}


def _user(db: Session, *, email: str = "op@x.edu") -> User:
    user = User(email=email, display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session, *, code: str, actor: User | None = None
) -> ReviewSession:
    actor = actor or _user(db, email=f"{code}@x.edu")
    review_session = ReviewSession(
        name="DS",
        code=code,
        created_by_user_id=actor.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(
    db: Session, review_session: ReviewSession, *, short_label: str = "Peer"
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id,
        name="Peer review",
        short_label=short_label,
    )
    db.add(instrument)
    db.flush()
    return instrument


def _field(
    db: Session, instrument: Instrument, *, field_key: str = "score"
) -> InstrumentResponseField:
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=field_key.title(),
        order=0,
        **_INLINE_NUMERIC,
    )
    db.add(field)
    db.flush()
    return field


def _seed_three_shapes(
    db: Session, review_session: ReviewSession
) -> tuple[Instrument, InstrumentResponseField]:
    instrument = _instrument(
        db, review_session, short_label="Peer Review"
    )
    field = _field(db, instrument, field_key="score")

    # Shape 1 — session-wide (no scope).
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Whole roster",
            axis="reviewer",
            instrument_id=None,
            response_field_id=None,
            column_chip_slots=json.dumps(
                ["reviewer:name", "reviewer:email"]
            ),
        )
    )
    # Shape 2 — scoped to an instrument.
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Per instrument",
            axis="reviewer",
            instrument_id=instrument.id,
            response_field_id=None,
            column_chip_slots=json.dumps(
                ["reviewer:name", "reviewer:count"]
            ),
        )
    )
    # Shape 3 — scoped to a specific response field.
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Per field",
            axis="reviewee",
            instrument_id=instrument.id,
            response_field_id=field.id,
            column_chip_slots=json.dumps(
                ["reviewee:name", "reviewee:mean"]
            ),
        )
    )
    db.flush()
    return instrument, field


def test_export_serialises_all_three_shape_variants(
    db: Session,
) -> None:
    review_session = _session(db, code="export")
    _seed_three_shapes(db, review_session)
    rows = session_config_io.serialize_session_config(db, review_session)
    shape_rows = [r for r in rows if r.field.startswith("data_shapes[")]
    # 5 rows per shape × 3 shapes = 15
    assert len(shape_rows) == 15
    by_field = {r.field: r.value for r in shape_rows}
    # Shapes sorted by name → 0: Per field, 1: Per instrument,
    # 2: Whole roster.
    assert by_field["data_shapes[0].name"] == "Per field"
    assert by_field["data_shapes[1].name"] == "Per instrument"
    assert by_field["data_shapes[2].name"] == "Whole roster"
    # Portable references — instrument's short_label and
    # response field's field_key, not their FKs.
    assert (
        by_field["data_shapes[0].instrument_short_label"]
        == "Peer Review"
    )
    assert by_field["data_shapes[0].response_field_key"] == "score"
    # "Per instrument" carries the instrument ref but no field
    # ref.
    assert (
        by_field["data_shapes[1].instrument_short_label"]
        == "Peer Review"
    )
    assert by_field["data_shapes[1].response_field_key"] == ""
    # "Whole roster" carries neither.
    assert by_field["data_shapes[2].instrument_short_label"] == ""
    assert by_field["data_shapes[2].response_field_key"] == ""


def test_roundtrip_applies_shapes_with_portable_references(
    db: Session,
) -> None:
    """Export from session A, apply onto session B (which has
    instruments + fields with matching short_label /
    field_key), and confirm the shapes come back with the new
    session's FKs."""
    session_a = _session(db, code="src")
    _seed_three_shapes(db, session_a)
    rows = session_config_io.serialize_session_config(db, session_a)

    # Build a destination session with matching short_label /
    # field_key so the references resolve.
    session_b = _session(db, code="dst")
    instr_b = _instrument(
        db, session_b, short_label="Peer Review"
    )
    field_b = _field(db, instr_b, field_key="score")
    db.flush()

    result = session_config_io.apply_session_config(
        db, session_b, list(rows), user=None
    )
    assert result.ok, result.errors
    db.expire_all()

    shapes_b = list(
        db.execute(
            select(DataShape)
            .where(DataShape.session_id == session_b.id)
            .order_by(DataShape.name)
        ).scalars()
    )
    assert len(shapes_b) == 3
    by_name = {s.name: s for s in shapes_b}
    # Session-wide shape — FKs stay null.
    assert by_name["Whole roster"].instrument_id is None
    assert by_name["Whole roster"].response_field_id is None
    # Instrument-scoped shape — FK resolves to session B's
    # ``Peer Review`` instrument.
    assert by_name["Per instrument"].instrument_id == instr_b.id
    assert by_name["Per instrument"].response_field_id is None
    # Field-scoped shape — FK resolves to session B's
    # ``score`` field.
    assert by_name["Per field"].instrument_id == instr_b.id
    assert by_name["Per field"].response_field_id == field_b.id
    # Column slots round-trip JSON-stable.
    assert json.loads(by_name["Per field"].column_chip_slots) == [
        "reviewee:name",
        "reviewee:mean",
    ]


def test_apply_wipes_existing_shapes_before_replacing(
    db: Session,
) -> None:
    """The applier replaces (not merges) saved shapes — a
    pre-existing shape on the destination not present in the
    incoming CSV is wiped."""
    session_a = _session(db, code="repl-src")
    _seed_three_shapes(db, session_a)
    rows = session_config_io.serialize_session_config(db, session_a)

    session_b = _session(db, code="repl-dst")
    instr_b = _instrument(db, session_b, short_label="Peer Review")
    _field(db, instr_b, field_key="score")
    # Pre-existing shape on B that's NOT in the import.
    db.add(
        DataShape(
            session_id=session_b.id,
            name="Stale",
            axis="reviewer",
            instrument_id=None,
            response_field_id=None,
            column_chip_slots=json.dumps(["reviewer:name"]),
        )
    )
    db.flush()

    session_config_io.apply_session_config(
        db, session_b, list(rows), user=None
    )
    db.expire_all()

    names = {
        s.name
        for s in db.execute(
            select(DataShape).where(DataShape.session_id == session_b.id)
        ).scalars()
    }
    assert "Stale" not in names
    assert names == {"Whole roster", "Per instrument", "Per field"}
