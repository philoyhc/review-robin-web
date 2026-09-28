"""19T Item 13 rung 2 — ``branch_mode`` is stored and copied, but nothing
writes it yet: clone and Replicate instrument carry a parent's mode, while
the card's save ignores one and the settings CSV refuses one until the
rule reads it (rung 3; Codex on #2671)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentResponseField, User
from app.services import instruments as instruments_service
from app.services import session_clone
from app.services.session_config_io import Row, apply_session_config, serialize_session_config

from .test_response_field_branching_roundtrip import (
    _branched_instrument,
    _fields,
    _session,
)
from .test_response_field_branching_save import _branched, _rfs, _save


def test_replicate_instrument_copies_the_mode(db: Session) -> None:
    review_session, op = _session(db, "13-replicate")
    source = _branched_instrument(db, review_session)
    _fields(db, source.id)["colour"].branch_mode = "require"
    db.flush()
    copy = instruments_service.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    fields = _fields(db, copy.id)
    assert fields["colour"].branch_mode == "require"
    assert fields["why"].branch_mode is None and fields["notes"].branch_mode is None


def test_clone_copies_the_mode(client: TestClient, db: Session) -> None:
    review_session, _, rating, _ = _branched(client, db, "13-clone")
    rating.branch_mode = "require"
    db.commit()
    user = db.execute(select(User)).scalars().first()
    clone = session_clone.clone_session(db, source=review_session, user=user, mode="all")
    db.flush()
    cloned = db.execute(
        select(InstrumentResponseField)
        .join(Instrument)
        .where(Instrument.session_id == clone.id, InstrumentResponseField.label == "Rating")
    ).scalars().all()
    assert [f.branch_mode for f in cloned if f.branch_op] == ["require"]


def test_the_cards_save_ignores_a_mode(client: TestClient, db: Session) -> None:
    review_session, instrument, rating, _ = _branched(client, db, "13-save")
    response = _save(client, review_session, instrument, _rfs(
        instrument, Rating={"branch_mode": "require"},
    ))
    assert response.status_code == 200, response.text
    db.refresh(rating)
    assert (rating.branch_op, rating.branch_mode) == ("ge", None)


def test_the_settings_csv_neither_exports_nor_imports_a_mode(db: Session) -> None:
    source, _ = _session(db, "13-csv-src")
    instrument = _branched_instrument(db, source)
    _fields(db, instrument.id)["colour"].branch_mode = "require"
    db.flush()
    rows = serialize_session_config(db, source)
    assert not [r for r in rows if r.field.endswith(".branch_mode")]
    # An imported ``branch_mode`` row is refused by name, as an unknown
    # response-field attribute, until rung 3 teaches the importer.
    rows = [r for r in rows if r.field.startswith("instruments")] + [
        Row(
            field="instruments[1].response_fields[1].branch_mode",
            value="require",
            data_type="enum",
        )
    ]
    target, _ = _session(db, "13-csv-dst")
    result = apply_session_config(db, target, rows)
    assert [(e.field, e.message) for e in result.errors] == [(
        "instruments[1].response_fields[1].branch_mode",
        "unknown response_fields[] attribute 'branch_mode'",
    )]
    assert not db.execute(
        select(InstrumentResponseField.branch_mode)
        .join(Instrument)
        .where(
            Instrument.session_id == target.id,
            InstrumentResponseField.branch_mode.is_not(None),
        )
    ).all()
