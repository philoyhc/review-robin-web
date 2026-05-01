from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    ReviewSession,
    User,
)
from app.services.instruments import (
    DisplaySourceError,
    add_display_field,
    bulk_save_fields,
    delete_display_field,
    ensure_default_instrument,
    update_display_field,
)


def _user(db: Session) -> User:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User, *, code: str) -> ReviewSession:
    s = ReviewSession(name="Test", code=code, created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _seed_pair_context_display_fields(db: Session, instrument: Instrument) -> None:
    for slot, order in (("1", 0), ("2", 1), ("3", 2)):
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="pair_context",
                source_field=slot,
                order=order,
                visible=True,
            )
        )
    db.flush()


def _seed_instrument(db: Session, code: str) -> tuple[User, Instrument]:
    user = _user(db)
    session = _session(db, user, code=code)
    instrument = ensure_default_instrument(db, session)
    # Most tests in this module assume the legacy behaviour where the
    # three pair_context display fields exist post-creation. After the
    # 2026-05-01 lazy-seed change (item #14), the fixture seeds them
    # explicitly so individual tests stay focused on the behaviour they
    # exercise.
    _seed_pair_context_display_fields(db, instrument)
    return user, instrument


def test_add_display_field_rejects_unknown_source_pair(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="add-unknown")

    with pytest.raises(DisplaySourceError):
        add_display_field(
            db,
            instrument=instrument,
            source_type="reviewee",
            source_field="phone",
            label="",
            visible=True,
            actor=user,
        )

    rows = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "phone",
        )
    ).scalars().all()
    assert rows == []


def test_add_display_field_rejects_duplicate_pair(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="add-dup")
    # ensure_default_instrument seeds (pair_context, "1") already

    with pytest.raises(DisplaySourceError):
        add_display_field(
            db,
            instrument=instrument,
            source_type="pair_context",
            source_field="1",
            label="",
            visible=True,
            actor=user,
        )

    pair_one = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_type == "pair_context",
            InstrumentDisplayField.source_field == "1",
        )
    ).scalars().all()
    assert len(pair_one) == 1


def test_add_display_field_appends_packed_order_and_audits(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="add-append")
    # seeded: pair_context 1/2/3 at orders 0/1/2

    new_field = add_display_field(
        db,
        instrument=instrument,
        source_type="reviewee",
        source_field="tag_1",
        label="  Cohort  ",
        visible=True,
        actor=user,
    )

    assert new_field.order == 3
    assert new_field.label == "Cohort"

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [r.order for r in rows] == [0, 1, 2, 3]

    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.display_field_added"
        )
    ).scalars().all()
    assert len(events) == 1
    detail = events[0].detail
    assert detail["source_type"] == "reviewee"
    assert detail["source_field"] == "tag_1"
    assert detail["label"] == "Cohort"
    assert detail["order"] == 3
    assert detail["visible"] is True


def test_update_display_field_records_only_changed_keys(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="upd-changes")
    field = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "1")
    )

    # Flip both label and visibility
    _, changes = update_display_field(
        db, field=field, label="P1", visible=False, actor=user
    )
    assert changes == {
        "label": ["", "P1"],
        "visible": [True, False],
    }

    # Second call: no-op edit -> empty changes dict, but still emits one event
    _, changes2 = update_display_field(
        db, field=field, label="P1", visible=False, actor=user
    )
    assert changes2 == {}

    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.display_field_updated"
        )
    ).scalars().all()
    assert len(events) == 2
    assert events[1].detail["changes"] == {}


def test_update_display_field_strips_label(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="upd-strip")
    field = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "2")
    )

    update_display_field(
        db, field=field, label="  Hi  ", visible=True, actor=user
    )
    assert field.label == "Hi"


def test_delete_display_field_repacks_and_audits(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="del-repack")
    pair_two = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "2")
    )

    delete_display_field(db, field=pair_two, actor=user)

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_field, r.order) for r in rows] == [("1", 0), ("3", 1)]

    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.display_field_deleted"
        )
    ).scalars().all()
    assert len(events) == 1
    snapshot = events[0].detail["snapshot"]
    assert snapshot["source_type"] == "pair_context"
    assert snapshot["source_field"] == "2"


def test_bulk_save_fields_repacks_per_table_independently(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="bulk-repack")
    # response fields seeded: rating @ order=0 (after 10A repack), comments @ 1
    # display fields seeded: pair_context 1/2/3 @ 0/1/2

    rating = next(
        f for f in instrument.response_fields if f.field_key == "rating"
    )
    comments = next(
        f for f in instrument.response_fields if f.field_key == "comments"
    )
    pc_one = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "1")
    )
    pc_two = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "2")
    )

    # Submit only some rows in an interleaved order:
    # [display(pc_one) @ submitted-pos 0, response(rating) @ 1,
    #  display(pc_two) @ 2, response(comments) @ 3]
    # bulk_save_fields uses submission order — each per-table list should
    # repack to 0..N-1 independently regardless of the absolute positions.
    rows = [
        {"kind": "display", "id": pc_one.id, "order": 0, "label": "", "visible": True},
        {"kind": "response", "id": rating.id, "order": 1},
        {"kind": "display", "id": pc_two.id, "order": 2, "label": "", "visible": True},
        {"kind": "response", "id": comments.id, "order": 3},
    ]
    summary = bulk_save_fields(db, instrument=instrument, rows=rows, actor=user)

    db.refresh(pc_one)
    db.refresh(pc_two)
    db.refresh(rating)
    db.refresh(comments)
    assert pc_one.order == 0
    assert pc_two.order == 1
    assert rating.order == 0
    assert comments.order == 1
    assert summary == {"display_changed": False, "response_order_changed": False}


def test_bulk_save_fields_emits_fields_reordered_when_response_order_changes(
    db: Session,
) -> None:
    user, instrument = _seed_instrument(db, code="bulk-resp-reorder")
    rating = next(
        f for f in instrument.response_fields if f.field_key == "rating"
    )
    comments = next(
        f for f in instrument.response_fields if f.field_key == "comments"
    )

    # Swap response order: comments before rating
    rows = [
        {"kind": "response", "id": comments.id, "order": 0},
        {"kind": "response", "id": rating.id, "order": 1},
    ]
    summary = bulk_save_fields(db, instrument=instrument, rows=rows, actor=user)

    assert summary["response_order_changed"] is True

    events = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.fields_reordered")
        .order_by(AuditEvent.id)
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail["old_order"] == ["rating", "comments"]
    assert events[0].detail["new_order"] == ["comments", "rating"]


def test_bulk_save_fields_emits_display_fields_saved_with_diff(
    db: Session,
) -> None:
    user, instrument = _seed_instrument(db, code="bulk-disp-diff")
    pc_one = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "1")
    )
    pc_two = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "2")
    )
    pc_three = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "3")
    )

    # Toggle pc_two visibility off, change pc_one label, leave pc_three alone
    rows = [
        {"kind": "display", "id": pc_one.id, "order": 0, "label": "P1", "visible": True},
        {"kind": "display", "id": pc_two.id, "order": 1, "label": "", "visible": False},
        {"kind": "display", "id": pc_three.id, "order": 2, "label": "", "visible": True},
    ]
    summary = bulk_save_fields(db, instrument=instrument, rows=rows, actor=user)

    assert summary["display_changed"] is True
    assert summary["response_order_changed"] is False

    events = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.display_fields_saved")
    ).scalars().all()
    assert len(events) == 1
    detail = events[0].detail
    assert detail["added"] == []
    assert detail["removed"] == []
    updated = {(e["source_type"], e["source_field"]): e["changes"] for e in detail["updated"]}
    assert updated == {
        ("pair_context", "1"): {"label": ["", "P1"]},
        ("pair_context", "2"): {"visible": [True, False]},
    }


def test_bulk_save_fields_no_op_emits_zero_events(db: Session) -> None:
    user, instrument = _seed_instrument(db, code="bulk-noop")
    pc_one = next(
        f for f in instrument.display_fields
        if (f.source_type, f.source_field) == ("pair_context", "1")
    )
    rating = next(
        f for f in instrument.response_fields if f.field_key == "rating"
    )

    # Submit current state — no actual changes
    rows = [
        {"kind": "display", "id": pc_one.id, "order": 0, "label": "", "visible": True},
        {"kind": "response", "id": rating.id, "order": 0},
    ]
    summary = bulk_save_fields(db, instrument=instrument, rows=rows, actor=user)

    assert summary == {"display_changed": False, "response_order_changed": False}

    events = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.event_type.in_(
                [
                    "instrument.fields_reordered",
                    "instrument.display_fields_saved",
                ]
            )
        )
    ).scalars().all()
    assert events == []
