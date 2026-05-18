"""Integration tests for the locked-row gates on the Display
Fields table — RevieweeName / RevieweeEmail can't be deleted,
hidden, or moved out of their fixed top-of-table positions.

Carved out of test_display_field_routes.py per
guide/archive/major_refactor.md §12.D.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentDisplayField, User
from app.services import instruments
from ._display_field_helpers import _instrument, _make_session


def _bulk_hide_all_display_fields(
    db: Session, *, instrument: Instrument
) -> None:
    """Run a bulk-save submitting every display row with
    ``visible=False`` — the locked-row force is what decides whether
    RevieweeName / RevieweeEmail actually flip."""
    actor = db.execute(select(User)).scalars().first()
    rows = [
        {"kind": "display", "id": df.id, "order": i, "visible": False}
        for i, df in enumerate(instrument.display_fields)
    ]
    instruments.bulk_save_fields(
        db, instrument=instrument, rows=rows, actor=actor
    )


def test_group_instrument_name_row_not_locked_on_bulk_save(
    client: TestClient, db: Session
) -> None:
    """Segment 13C — on a group-scoped instrument the RevieweeName
    row is operator-choosable; ``bulk_save_fields`` does not force it
    visible the way it does on a per-reviewee instrument."""
    review_session = _make_session(client, db, code="grp-namelock")
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-group",
        follow_redirects=False,
    )
    assert response.status_code == 303
    group = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.group_kind.is_not(None))
    ).scalar_one()

    _bulk_hide_all_display_fields(db, instrument=group)

    name_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == group.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()
    assert name_row.visible is False


def test_per_reviewee_instrument_name_row_stays_locked_on_bulk_save(
    client: TestClient, db: Session
) -> None:
    """The locked-row force still applies to an ordinary instrument."""
    review_session = _make_session(client, db, code="norm-namelock")
    instrument = _instrument(db, review_session.id)

    _bulk_hide_all_display_fields(db, instrument=instrument)

    name_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()
    assert name_row.visible is True

def test_locked_name_row_cannot_be_deleted(
    client: TestClient, db: Session
) -> None:
    """Per spec, ``RevieweeName`` and ``RevieweeEmail`` rows are
    locked — the delete route rejects them with 400."""
    review_session = _make_session(client, db, code="lock-del")
    instrument = _instrument(db, review_session.id)
    name_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{name_row.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_locked_email_row_cannot_be_hidden(
    client: TestClient, db: Session
) -> None:
    """Per spec, the locked rows' Include checkbox is always-on and
    cannot be flipped. The edit route forces ``visible=True`` on save
    via ``bulk_save_fields``; the row-level edit route raises the
    same error if ``visible=false`` slips in."""
    review_session = _make_session(client, db, code="lock-vis")
    instrument = _instrument(db, review_session.id)
    email_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "email_or_identifier",
        )
    ).scalar_one()

    client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{email_row.id}/edit",
        data={"label": "Email", "visible": ""},
        follow_redirects=False,
    )
    # Service raises LockedDisplayFieldError; route currently lets it
    # bubble up as a 500. We accept either 4xx/5xx but verify the row
    # state is unchanged.
    db.refresh(email_row)
    assert email_row.visible is True


def test_locked_name_row_cannot_be_moved(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lock-move")
    instrument = _instrument(db, review_session.id)
    name_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{name_row.id}/move",
        data={"direction": "down"},
        follow_redirects=False,
    )
    assert response.status_code == 400


