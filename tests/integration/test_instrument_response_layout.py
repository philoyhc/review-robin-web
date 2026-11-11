"""Segment 20K — an instrument picks how its response fields are laid out.

``Instrument.response_layout`` is ``columns`` (a column per response
field; the default) or ``stacked`` (one field per line in a single
cell). Rung 2 stores it: the setter, its audit event and the revert of a
validated session, Replicate, Duplicate and the Settings CSV. Nothing
renders it yet.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.db.models.instrument import RESPONSE_LAYOUT_DEFAULT, RESPONSE_LAYOUTS
from app.services import session_clone
from app.services.instruments import (
    ResponseLayoutError,
    effective_response_layout,
    ensure_default_instrument,
    is_untouched_default,
    replicate_instrument,
    set_response_layout,
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
    review_session = ReviewSession(name="20K", code=code, created_by_user_id=user.id)
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
            .where(AuditEvent.event_type == "instrument.response_layout_set")
            .order_by(AuditEvent.id)
        ).scalars()
    )


def test_columns_is_the_default_and_first_in_the_cycle() -> None:
    assert RESPONSE_LAYOUTS == ("columns", "stacked")
    assert RESPONSE_LAYOUT_DEFAULT == "columns"


def test_a_new_instrument_takes_columns(db: Session) -> None:
    _, _, instrument = _seed(db, code="20k-default")
    assert instrument.response_layout == "columns"


def test_a_stray_stored_value_reads_as_columns() -> None:
    assert effective_response_layout(Instrument(response_layout="stacked")) == "stacked"
    assert effective_response_layout(Instrument(response_layout="sideways")) == "columns"


def test_the_setter_stores_audits_and_skips_a_no_op(db: Session) -> None:
    user, _, instrument = _seed(db, code="20k-setter")
    set_response_layout(db, instrument=instrument, layout="stacked", actor=user)
    set_response_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert instrument.response_layout == "stacked"
    events = _layout_events(db)
    assert len(events) == 1
    assert events[0].detail is not None
    assert events[0].detail["changes"] == {"response_layout": ["columns", "stacked"]}
    assert events[0].detail["refs"] == {"instrument_id": instrument.id}


def test_the_setter_refuses_an_unknown_layout(db: Session) -> None:
    user, _, instrument = _seed(db, code="20k-unknown")
    with pytest.raises(ResponseLayoutError):
        set_response_layout(db, instrument=instrument, layout="sideways", actor=user)
    assert instrument.response_layout == "columns"
    assert _layout_events(db) == []


def test_a_change_reverts_a_validated_session_and_a_no_op_does_not(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20k-validated")
    review_session.status = "validated"
    db.commit()
    set_response_layout(db, instrument=instrument, layout="columns", actor=user)
    assert review_session.status == "validated"
    set_response_layout(db, instrument=instrument, layout="stacked", actor=user)
    db.commit()
    assert review_session.status == "draft"
    invalidated = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.invalidated")
    ).scalar_one()
    assert invalidated.detail is not None
    assert invalidated.detail["reason"] == "instrument_response_layout_set"


def test_a_stacked_instrument_is_not_the_untouched_default(db: Session) -> None:
    _, _, instrument = _seed(db, code="20k-untouched")
    assert is_untouched_default(instrument)
    instrument.response_layout = "stacked"
    assert not is_untouched_default(instrument)


def test_replicate_carries_the_layout(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="20k-repl")
    instrument.response_layout = "stacked"
    db.commit()
    replica = replicate_instrument(db, review_session=review_session, source=instrument, actor=user)
    assert replica.response_layout == "stacked"


def test_duplicate_carries_each_instruments_layout(db: Session) -> None:
    user, review_session, first = _seed(db, code="20k-dup")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.response_layout = "stacked"
    db.commit()
    clone = session_clone.clone_session(db, source=review_session, user=user, mode="config")
    layouts = dict(
        db.execute(
            select(Instrument.name, Instrument.response_layout).where(
                Instrument.session_id == clone.id
            )
        ).all()
    )
    assert layouts == {first.name: "stacked", "Second": "columns"}


def test_settings_csv_round_trip_carries_each_instruments_layout(db: Session) -> None:
    _, source, first = _seed(db, code="20k-csv-src")
    second = Instrument(session_id=source.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.response_layout = "stacked"
    db.commit()

    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    assert by_field["instruments[1].response_layout"] == Row(
        "instruments[1].response_layout", "stacked", "enum"
    )
    assert by_field["instruments[2].response_layout"].value == "columns"

    destination = _bare(db, "20k-csv-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    layouts = [
        layout
        for (layout,) in db.execute(
            select(Instrument.response_layout)
            .where(Instrument.session_id == destination.id)
            .order_by(Instrument.order)
        ).all()
    ]
    assert layouts == ["stacked", "columns"]


def test_an_older_settings_csv_takes_the_default(db: Session) -> None:
    destination = _bare(db, "20k-csv-old")
    result = apply_session_config(db, destination, [Row("instruments[1].name", "Eval", "string")])
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert instrument.response_layout == "columns"


def test_the_settings_csv_refuses_an_unknown_layout(db: Session) -> None:
    destination = _bare(db, "20k-csv-bad")
    result = apply_session_config(
        db,
        destination,
        [
            Row("instruments[1].name", "Eval", "string"),
            Row("instruments[1].response_layout", "sideways", "enum"),
        ],
    )
    assert not result.ok
    assert any("response_layout" in str(error) for error in result.errors)


def test_a_stray_stored_value_exports_as_columns(db: Session) -> None:
    _, review_session, instrument = _seed(db, code="20k-stray")
    instrument.response_layout = "sideways"
    db.commit()
    rows = serialize_session_config(db, review_session)
    assert {r.field: r.value for r in rows}["instruments[1].response_layout"] == "columns"
