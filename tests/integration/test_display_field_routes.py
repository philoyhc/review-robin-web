"""Integration tests for the display-field builder routes (Segment 10B-2)."""

from __future__ import annotations


from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    InstrumentDisplayField,
)
from ._display_field_helpers import (
    _activate,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _populate_rosters,
    _seed_pair_context_display_fields,
    _validate,
)




def test_add_display_field_appends_row_and_invalidates_validated(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="add-disp")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    _validate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "validated"

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields",
        data={"source_pair": "reviewee:tag_1", "label": "Cohort", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_type, r.source_field) for r in rows] == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("pair_context", "1"),
        ("pair_context", "2"),
        ("pair_context", "3"),
        ("reviewee", "tag_1"),
    ]
    new_row = rows[-1]
    assert new_row.label == "Cohort"
    assert new_row.visible is True
    assert new_row.order == 5

    db.refresh(review_session)
    assert review_session.status == "draft"
    invalidated = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.invalidated",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(invalidated) == 1


def test_add_display_field_unknown_source_redirects_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="add-unknown")
    instrument = _instrument(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields",
        data={"source_pair": "reviewee:phone", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "display_source_error=reviewee:phone" in response.headers["location"]


def test_add_display_field_duplicate_source_redirects_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="add-dup")
    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields",
        data={"source_pair": "pair_context:1", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "display_source_error=pair_context:1" in response.headers["location"]

    pair_one_count = db.execute(
        select(InstrumentDisplayField)
        .where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_type == "pair_context",
            InstrumentDisplayField.source_field == "1",
        )
    ).scalars().all()
    assert len(pair_one_count) == 1


def test_edit_display_field_updates_label_and_visibility(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="edit-disp")
    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    pair_one = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "1",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{pair_one.id}/edit",
        data={"label": "P1", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(pair_one)
    assert pair_one.label == "P1"
    assert pair_one.visible is True

    # Now flip visible off
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{pair_one.id}/edit",
        data={"label": "P1"},  # no visible -> false
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(pair_one)
    assert pair_one.visible is False


def test_delete_display_field_removes_row_and_repacks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="del-disp")
    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    pair_two = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "2",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{pair_two.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    # Locked Name + Email rows kept at 0/1; pc_1 + pc_3 repack to 2/3.
    assert [(r.source_type, r.source_field, r.order) for r in rows] == [
        ("reviewee", "name", 0),
        ("reviewee", "email_or_identifier", 1),
        ("pair_context", "1", 2),
        ("pair_context", "3", 3),
    ]


def test_locked_when_ready_returns_409_for_display_field_routes(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="lock-disp")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"

    pair_one = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "1",
        )
    ).scalar_one()

    add = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields",
        data={"source_pair": "reviewee:tag_1", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    assert add.status_code == 409

    edit = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{pair_one.id}/edit",
        data={"label": "X", "visible": "true"},
        follow_redirects=False,
    )
    assert edit.status_code == 409

    delete = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{pair_one.id}/delete",
        follow_redirects=False,
    )
    assert delete.status_code == 409

    bulk = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/save",
        data={"kind": ["display"], "id": [str(pair_one.id)], "order": ["0"]},
        follow_redirects=False,
    )
    assert bulk.status_code == 409



def test_move_display_field_swap_preserves_locked_top(
    client: TestClient, db: Session
) -> None:
    """Moving a non-locked row up never crosses into the locked region
    (Name + Email always stay at orders 0 / 1)."""
    review_session = _make_session(client, db, code="move-swap")
    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    pc_two = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "2",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{pc_two.id}/move",
        data={"direction": "up"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    # Editing-mode preserved on the redirect.
    assert f"editing={instrument.id}" in response.headers["location"]

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    # Name + Email at top; pc_2 swapped above pc_1.
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("pair_context", "2"),
        ("pair_context", "1"),
        ("pair_context", "3"),
    ]

