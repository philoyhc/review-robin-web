"""Segment 20M rung 3 — where an instrument's display fields sit.

``Instrument.display_layout`` is ``across`` (a column per display field;
the default), ``stacked`` or ``joined`` (under the reviewee). This rung
stores it: the setter, its audit event and the revert of a validated
session, Replicate, Duplicate and the Settings CSV. Nothing renders it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.db.models.instrument import DISPLAY_LAYOUT_DEFAULT, DISPLAY_LAYOUTS
from app.services import session_clone
from app.services.instruments import (
    DisplayLayoutError,
    effective_display_layout,
    ensure_default_instrument,
    is_untouched_default,
    replicate_instrument,
    set_display_layout,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _seed(db: Session, *, code: str) -> tuple[User, ReviewSession, Instrument]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="20M", code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    db.commit()
    return user, review_session, instrument


def _bare(db: Session, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name=code, code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    return review_session


def _layout_events(db: Session) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "instrument.display_layout_set")
            .order_by(AuditEvent.id)
        ).scalars()
    )


def test_across_is_the_default_and_first_in_the_cycle() -> None:
    assert DISPLAY_LAYOUTS == ("across", "stacked", "joined")
    assert DISPLAY_LAYOUT_DEFAULT == "across"


def test_a_new_instrument_takes_across(db: Session) -> None:
    _, _, instrument = _seed(db, code="20m-default")
    assert instrument.display_layout == "across"


def test_a_stray_stored_value_reads_as_across() -> None:
    assert effective_display_layout(Instrument(display_layout="stacked")) == "stacked"
    assert effective_display_layout(Instrument(display_layout="sideways")) == "across"


def test_the_setter_stores_audits_and_skips_a_no_op(db: Session) -> None:
    user, _, instrument = _seed(db, code="20m-setter")
    set_display_layout(db, instrument=instrument, layout="stacked", actor=user)
    set_display_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert instrument.display_layout == "stacked"
    events = _layout_events(db)
    assert len(events) == 1
    assert events[0].detail is not None
    assert events[0].detail["changes"] == {"display_layout": ["across", "stacked"]}
    assert events[0].detail["refs"] == {"instrument_id": instrument.id}


def test_the_setter_refuses_an_unknown_layout(db: Session) -> None:
    user, _, instrument = _seed(db, code="20m-unknown")
    with pytest.raises(DisplayLayoutError):
        set_display_layout(db, instrument=instrument, layout="sideways", actor=user)
    assert instrument.display_layout == "across"
    assert _layout_events(db) == []


def test_a_change_reverts_a_validated_session_and_a_no_op_does_not(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20m-validated")
    review_session.status = "validated"
    db.commit()
    set_display_layout(db, instrument=instrument, layout="across", actor=user)
    assert review_session.status == "validated"
    set_display_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert review_session.status == "draft"
    invalidated = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.invalidated")
    ).scalar_one()
    assert invalidated.detail is not None
    assert invalidated.detail["reason"] == "instrument_display_layout_set"


def test_a_stacked_instrument_is_not_the_untouched_default(db: Session) -> None:
    _, _, instrument = _seed(db, code="20m-untouched")
    assert is_untouched_default(instrument)
    instrument.display_layout = "stacked"
    assert not is_untouched_default(instrument)


def test_replicate_carries_the_layout(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20m-repl")
    instrument.display_layout = "stacked"
    db.commit()
    replica = replicate_instrument(db, review_session=review_session, source=instrument, actor=user)
    assert replica.display_layout == "stacked"


def test_duplicate_carries_each_instruments_layout(db: Session) -> None:
    user, review_session, first = _seed(db, code="20m-dup")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.display_layout = "stacked"
    db.commit()
    clone = session_clone.clone_session(db, source=review_session, user=user, mode="config")
    layouts = dict(
        db.execute(
            select(Instrument.name, Instrument.display_layout).where(
                Instrument.session_id == clone.id
            )
        ).all()
    )
    assert layouts == {first.name: "stacked", "Second": "across"}


def test_settings_csv_round_trip_carries_each_instruments_layout(db: Session) -> None:
    _, source, first = _seed(db, code="20m-csv-src")
    second = Instrument(session_id=source.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.display_layout = "stacked"
    db.commit()

    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    assert by_field["instruments[1].display_layout"] == Row(
        "instruments[1].display_layout", "stacked", "enum"
    )
    assert by_field["instruments[2].display_layout"].value == "across"

    destination = _bare(db, "20m-csv-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    layouts = [
        layout
        for (layout,) in db.execute(
            select(Instrument.display_layout)
            .where(Instrument.session_id == destination.id)
            .order_by(Instrument.order)
        ).all()
    ]
    assert layouts == ["stacked", "across"]


def test_an_older_settings_csv_takes_the_default(db: Session) -> None:
    destination = _bare(db, "20m-csv-old")
    result = apply_session_config(db, destination, [Row("instruments[1].name", "Eval", "string")])
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert instrument.display_layout == "across"


def test_the_settings_csv_refuses_an_unknown_layout(db: Session) -> None:
    destination = _bare(db, "20m-csv-bad")
    result = apply_session_config(
        db,
        destination,
        [
            Row("instruments[1].name", "Eval", "string"),
            Row("instruments[1].display_layout", "sideways", "enum"),
        ],
    )
    assert not result.ok
    assert any("display_layout" in str(error) for error in result.errors)


def test_a_stray_stored_value_exports_as_across(db: Session) -> None:
    _, review_session, instrument = _seed(db, code="20m-stray")
    instrument.display_layout = "sideways"
    db.commit()
    rows = serialize_session_config(db, review_session)
    assert {r.field: r.value for r in rows}["instruments[1].display_layout"] == "across"
