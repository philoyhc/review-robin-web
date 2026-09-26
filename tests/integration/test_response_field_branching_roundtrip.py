"""19T Item 10 rung 5 — branches round-trip: the settings CSV carries a
parent by ``field_key`` and its condition, and Replicate instrument copies
the branch onto the copy. (Session clone re-points the parent since rung
2; ``test_response_field_branching_save.py`` covers it.)"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services import instruments as instruments_service
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(name=code, code=code, created_by_user_id=op.id)
    db.add(review_session)
    db.flush()
    return review_session, op


def _branched_instrument(db: Session, review_session: ReviewSession) -> Instrument:
    """Colour (List) governs Why while Colour is Red or Blue; Notes
    stays outside the branch."""
    instrument = Instrument(session_id=review_session.id, name="Survey", order=1)
    db.add(instrument)
    db.flush()
    colour = InstrumentResponseField(
        instrument_id=instrument.id, field_key="colour", label="Colour", order=1,
        _inline_data_type="List", _inline_response_type="List",
        _inline_list_csv="Red,Green,Blue", branch_op="is", branch_value="Red, Blue",
    )
    db.add(colour)
    db.flush()
    db.add_all([
        InstrumentResponseField(
            instrument_id=instrument.id, field_key="why", label="Why", order=2,
            _inline_data_type="String", _inline_response_type="Text",
            branch_parent_id=colour.id,
        ),
        InstrumentResponseField(
            instrument_id=instrument.id, field_key="notes", label="Notes", order=3,
            _inline_data_type="String", _inline_response_type="Text",
        ),
    ])
    db.flush()
    return instrument


def _fields(db: Session, instrument_id: int) -> dict[str, InstrumentResponseField]:
    return {
        f.field_key: f
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument_id
            )
        ).scalars()
    }


def test_the_settings_csv_exports_the_branch(db: Session) -> None:
    review_session, _ = _session(db, "br-csv-out")
    _branched_instrument(db, review_session)
    rows = {r.field: r for r in serialize_session_config(db, review_session)}
    prefix = "instruments[1].response_fields"
    assert rows[f"{prefix}[1].branch_op"].value == "is"
    assert rows[f"{prefix}[1].branch_op"].data_type == "enum"
    assert rows[f"{prefix}[1].branch_value"].value == "Red, Blue"
    assert rows[f"{prefix}[1].branch_parent"].value == ""
    assert rows[f"{prefix}[2].branch_parent"].value == "colour"
    assert rows[f"{prefix}[3].branch_parent"].value == ""


def test_the_settings_csv_round_trips_the_branch(db: Session) -> None:
    source, _ = _session(db, "br-csv-src")
    _branched_instrument(db, source)
    rows = serialize_session_config(db, source)
    target, _ = _session(db, "br-csv-dst")
    result = apply_session_config(
        db, target, [r for r in rows if r.field.startswith("instruments")]
    )
    assert result.errors == []
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == target.id)
    ).scalar_one()
    fields = _fields(db, instrument.id)
    assert (fields["colour"].branch_op, fields["colour"].branch_value) == (
        "is", "Red, Blue"
    )
    # The parent is re-pointed at the target's own field, by field_key.
    assert fields["why"].branch_parent_id == fields["colour"].id
    assert fields["notes"].branch_parent_id is None


def _rows() -> list[Row]:
    base = {
        "instruments[1].name": ("Survey", "string"),
        "instruments[1].response_fields[1].field_key": ("rating", "string"),
        "instruments[1].response_fields[1].label": ("Rating", "string"),
        "instruments[1].response_fields[1].response_type": ("Likert5", "string"),
        "instruments[1].response_fields[1].data_type": ("Integer", "string"),
        "instruments[1].response_fields[1].branch_op": ("ge", "enum"),
        "instruments[1].response_fields[1].branch_value": ("4", "string"),
        "instruments[1].response_fields[2].field_key": ("why", "string"),
        "instruments[1].response_fields[2].label": ("Why", "string"),
        "instruments[1].response_fields[2].response_type": ("Text", "string"),
        "instruments[1].response_fields[2].data_type": ("String", "string"),
        "instruments[1].response_fields[2].branch_parent": ("rating", "string"),
    }
    return [Row(field, value, data_type) for field, (value, data_type) in base.items()]


def test_the_settings_csv_refuses_a_broken_branch(db: Session) -> None:
    """Each rule is a named error from the parse phase; nothing applies."""
    review_session, _ = _session(db, "br-csv-bad")
    cases = {
        "instruments[1].response_fields[2].branch_parent": (
            "nope", "no response field 'nope' on this instrument",
            # …which also leaves Rating's condition governing nothing.
            "Rating: Its branch condition governs no field.",
        ),
        "instruments[1].response_fields[2].required": (
            "true", "Why: A field inside a branch can't be required."
        ),
        "instruments[1].response_fields[1].data_type": (
            "String", "Rating: A String field can't have a branch."
        ),
        "instruments[1].response_fields[1].branch_value": (
            "", "Rating: The branch condition needs a number."
        ),
    }
    for path, (value, *messages) in cases.items():
        rows = [
            Row(r.field, value, r.data_type) if r.field == path else r
            for r in _rows()
        ]
        if path not in {r.field for r in rows}:
            rows.append(Row(path, value, "boolean"))
        result = apply_session_config(db, review_session, rows)
        assert [e.message for e in result.errors] == messages, path
    # A lone branch_value, with no operator and no governed field, is an
    # orphaned condition (Codex on #2642).
    result = apply_session_config(
        db, review_session,
        [r for r in _rows()
         if not r.field.endswith(("branch_op", "branch_parent"))],
    )
    assert [e.message for e in result.errors] == [
        "Rating: Its branch condition governs no field."
    ]
    result = apply_session_config(
        db, review_session,
        [Row(r.field, "gte", r.data_type) if r.field.endswith("branch_op") else r
         for r in _rows()],
    )
    assert result.errors[0].message.startswith("unknown branch_op 'gte'")
    assert db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).first() is None


def test_replicate_instrument_copies_the_branch(db: Session) -> None:
    review_session, op = _session(db, "br-replicate")
    source = _branched_instrument(db, review_session)
    copy = instruments_service.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    fields = _fields(db, copy.id)
    source_fields = _fields(db, source.id)
    assert (fields["colour"].branch_op, fields["colour"].branch_value) == (
        "is", "Red, Blue"
    )
    assert fields["why"].branch_parent_id == fields["colour"].id
    assert fields["why"].branch_parent_id != source_fields["colour"].id
