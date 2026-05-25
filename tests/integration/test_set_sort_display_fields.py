"""Service-level coverage for
``instruments.set_sort_display_fields`` — Segment 13B PR 1.

Exercises the validator (length / dir / duplicates / cross-
instrument IDs), the no-op short-circuit, the lifecycle-
invalidation hook, and the canonical audit envelope on
``instrument.sort_fields_updated``.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, InstrumentDisplayField
from app.services import instruments
from app.services import session_lifecycle as lifecycle

from ._display_field_helpers import (
    _instrument,
    _make_session,
    _populate_rosters,
)


def _seed_two_display_fields(
    db: Session, instrument: Instrument
) -> tuple[InstrumentDisplayField, InstrumentDisplayField]:
    """Add two non-locked display fields so sort spec has something
    to reference. Mirrors the
    ``_seed_pair_context_display_fields`` helper but keeps the
    seed list lean."""
    existing_orders = [df.order for df in instrument.display_fields]
    base = max(existing_orders, default=-1) + 1
    f1 = InstrumentDisplayField(
        instrument_id=instrument.id,
        source_type="reviewee",
        source_field="tag_1",
        label="Tag 1",
        order=base,
        visible=True,
    )
    f2 = InstrumentDisplayField(
        instrument_id=instrument.id,
        source_type="reviewee",
        source_field="tag_2",
        label="Tag 2",
        order=base + 1,
        visible=True,
    )
    db.add_all([f1, f2])
    db.flush()
    return f1, f2


def _actor(db: Session):
    from app.db.models import User

    return db.execute(select(User)).scalars().first()


def test_set_sort_persists_canonical_shape(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ssdf-canon")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, f2 = _seed_two_display_fields(db, instrument)

    new_value, old_value = instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(f1.id, "asc"), (f2.id, "desc")],
        actor=_actor(db),
    )
    assert old_value is None
    assert new_value == [
        {"display_field_id": f1.id, "dir": "asc"},
        {"display_field_id": f2.id, "dir": "desc"},
    ]
    db.expire_all()
    refreshed = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert refreshed.sort_display_fields == new_value


def test_set_sort_accepts_canonical_dict_input(
    db: Session, client: TestClient
) -> None:
    """The route layer may hand in the canonical dict shape
    directly (e.g. when re-saving a value pulled from the DB)."""
    review_session = _make_session(client, db, code="ssdf-dict-in")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    new_value, _ = instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[{"display_field_id": f1.id, "dir": "asc"}],
        actor=_actor(db),
    )
    assert new_value == [{"display_field_id": f1.id, "dir": "asc"}]


def test_set_sort_clear_back_to_empty(
    db: Session, client: TestClient
) -> None:
    """Passing an empty list clears the sort back to the default
    'no operator sort' state."""
    review_session = _make_session(client, db, code="ssdf-clear")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(f1.id, "asc")],
        actor=_actor(db),
    )
    new_value, old_value = instruments.set_sort_display_fields(
        db, instrument=instrument, fields=[], actor=_actor(db)
    )
    assert old_value == [{"display_field_id": f1.id, "dir": "asc"}]
    assert new_value == []


def test_set_sort_rejects_too_many_keys(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ssdf-too-many")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, f2 = _seed_two_display_fields(db, instrument)
    # Seed a third display field to push past max.
    f3 = InstrumentDisplayField(
        instrument_id=instrument.id,
        source_type="reviewee",
        source_field="tag_3",
        label="Tag 3",
        order=max(df.order for df in instrument.display_fields) + 1,
        visible=True,
    )
    db.add(f3)
    db.flush()

    with pytest.raises(instruments.SortSpecError) as excinfo:
        instruments.set_sort_display_fields(
            db,
            instrument=instrument,
            fields=[
                (f1.id, "asc"),
                (f2.id, "asc"),
                (f3.id, "asc"),
                (f1.id, "desc"),
            ],
            actor=_actor(db),
        )
    assert excinfo.value.code == "too_many"


def test_set_sort_rejects_unknown_dir(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ssdf-bad-dir")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    with pytest.raises(instruments.SortSpecError) as excinfo:
        instruments.set_sort_display_fields(
            db,
            instrument=instrument,
            fields=[(f1.id, "sideways")],
            actor=_actor(db),
        )
    assert excinfo.value.code == "unknown_dir"


def test_set_sort_rejects_duplicate_id(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ssdf-dup")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    with pytest.raises(instruments.SortSpecError) as excinfo:
        instruments.set_sort_display_fields(
            db,
            instrument=instrument,
            fields=[(f1.id, "asc"), (f1.id, "desc")],
            actor=_actor(db),
        )
    assert excinfo.value.code == "duplicate_id"


def test_set_sort_rejects_cross_instrument_id(
    db: Session, client: TestClient
) -> None:
    """A display_field_id that belongs to a different
    instrument's display field set fails."""
    review_session = _make_session(client, db, code="ssdf-cross")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    _seed_two_display_fields(db, instrument)

    # Seed a second instrument with its own display field.
    other = Instrument(
        session_id=review_session.id, name="Other", order=99
    )
    db.add(other)
    db.flush()
    foreign = InstrumentDisplayField(
        instrument_id=other.id,
        source_type="reviewee",
        source_field="tag_1",
        label="Foreign",
        order=0,
        visible=True,
    )
    db.add(foreign)
    db.flush()

    with pytest.raises(instruments.SortSpecError) as excinfo:
        instruments.set_sort_display_fields(
            db,
            instrument=instrument,
            fields=[(foreign.id, "asc")],
            actor=_actor(db),
        )
    assert excinfo.value.code == "cross_instrument"


def test_set_sort_accepts_group_identity_sentinel(
    db: Session, client: TestClient
) -> None:
    """The ``GROUP_IDENTITY_SORT_KEY`` (-1) sentinel for the
    composed Group cell sort on a new-model group-scoped
    instrument's preview is exempt from the cross-instrument
    check — it isn't a real InstrumentDisplayField row."""
    review_session = _make_session(client, db, code="ssdf-group-sentinel")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)

    instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(instruments.GROUP_IDENTITY_SORT_KEY, "desc")],
        actor=_actor(db),
    )
    db.refresh(instrument)
    assert instrument.sort_display_fields == [
        {"display_field_id": -1, "dir": "desc"},
    ]


def test_set_sort_emits_audit_on_diff(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ssdf-audit")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(f1.id, "asc")],
        actor=_actor(db),
    )
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.sort_fields_updated",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = event.detail
    assert detail["refs"]["instrument_id"] == instrument.id
    assert detail["changes"] == {
        "sort_display_fields": [
            None,
            [{"display_field_id": f1.id, "dir": "asc"}],
        ]
    }


def test_set_sort_no_emit_on_noop_save(
    db: Session, client: TestClient
) -> None:
    """Idempotent: a second call with the same value emits no
    audit event."""
    review_session = _make_session(client, db, code="ssdf-noop")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(f1.id, "asc")],
        actor=_actor(db),
    )
    instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(f1.id, "asc")],
        actor=_actor(db),
    )
    events = (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "instrument.sort_fields_updated",
                AuditEvent.session_id == review_session.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1


def test_set_sort_invalidates_validated_session(
    db: Session, client: TestClient
) -> None:
    """Sort spec is a setup-shape change — saving it on a
    previously-validated session bumps it back to draft."""
    review_session = _make_session(client, db, code="ssdf-invalidate")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    f1, _ = _seed_two_display_fields(db, instrument)

    # Manually mark the session as validated.
    review_session.status = "validated"
    db.flush()
    assert lifecycle.is_validated(review_session)

    instruments.set_sort_display_fields(
        db,
        instrument=instrument,
        fields=[(f1.id, "asc")],
        actor=_actor(db),
    )
    db.expire_all()
    assert review_session.status == "draft"
