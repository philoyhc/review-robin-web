"""Integration tests for the display-field builder routes (Segment 10B-2)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ReviewSession,
)


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid",
        email="r@example.edu",
        name="R Reviewer",
        provider="aad",
    )


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _generate_full_matrix(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )


def _activate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")
    client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )


def _validate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")


def _instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


def _seed_pair_context_display_fields(db: Session, instrument: Instrument) -> None:
    """Pair-context display fields are no longer auto-seeded by
    ensure_default_instrument (item #14, 2026-05-01). Tests that
    exercise edit/delete on those rows seed them explicitly."""
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
    db.commit()


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
        ("pair_context", "1"),
        ("pair_context", "2"),
        ("pair_context", "3"),
        ("reviewee", "tag_1"),
    ]
    new_row = rows[-1]
    assert new_row.label == "Cohort"
    assert new_row.visible is True
    assert new_row.order == 3

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

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?display_source_error=reviewee:phone"
    ).text
    assert "Could not add display field" in body


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
    assert [(r.source_field, r.order) for r in rows] == [("1", 0), ("3", 1)]


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


def test_reviewees_import_lazy_seeds_display_fields(
    client: TestClient, db: Session
) -> None:
    """After uploading reviewees with populated tag/profile columns, the
    Default instrument should gain corresponding display-field rows
    automatically — no operator action required (item #14)."""
    review_session = _make_session(client, db, code="seed-on-import")
    instrument = _instrument(db, review_session.id)
    # Pre-condition: ensure_default_instrument no longer seeds anything.
    pre_rows = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id
        )
    ).scalars().all()
    assert pre_rows == []

    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail,RevieweeTag1,PhotoLink\n"
                    b"Carol,carol@example.edu,Cohort A,https://example.edu/c\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    assert pairs == [
        ("reviewee", "profile_link"),
        ("reviewee", "tag_1"),
    ]


def test_manual_assignments_import_lazy_seeds_pair_context_display_fields(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="seed-asgn-import")
    _populate_rosters(client, review_session.id)
    instrument = _instrument(db, review_session.id)

    client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "m.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContext1,PairContext2\n"
                    b"r@example.edu,carol@example.edu,morning,roomA\n"
                ),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    assert ("pair_context", "1") in pairs
    assert ("pair_context", "2") in pairs
    assert ("pair_context", "3") not in pairs


def test_friendly_label_persistence_round_trip_via_edit_route(
    client: TestClient, db: Session
) -> None:
    """The headline P0 fix: an operator-typed Friendly Label survives a
    page reload — it persists via the existing ``/display-fields/{id}/edit``
    route, not via the JS-only placeholder of yore (item #13)."""
    review_session = _make_session(client, db, code="lbl-persist")
    instrument = _instrument(db, review_session.id)
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="",
            source_type="reviewee",
            source_field="tag_1",
            order=0,
            visible=True,
        )
    )
    db.commit()
    df = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/display-fields/{df.id}/edit",
        data={"label": "Cohort", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(df)
    assert df.label == "Cohort"

    # Re-render the page; the operator's typed label should be visible
    # (not lost to a JS-only round-trip).
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Cohort" in body


def test_bulk_fields_save_interleaves_and_renders_on_reviewer_surface(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="bulk-render")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)

    instrument = _instrument(db, review_session.id)
    _seed_pair_context_display_fields(db, instrument)
    pair_one = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "1",
        )
    ).scalar_one()
    pair_two = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "2",
        )
    ).scalar_one()
    pair_three = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "3",
        )
    ).scalar_one()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    # Submit a hide on pair_two and a label override on pair_one.
    # Order doesn't change relative to seed; the form only flips
    # visibility + label here so we don't need to model the merged sort.
    payload = {
        "kind": ["display", "display", "display", "response", "response"],
        "id": [
            str(pair_one.id),
            str(pair_two.id),
            str(pair_three.id),
            str(rating.id),
            str(comments.id),
        ],
        "order": ["0", "1", "2", "3", "4"],
        "label": ["P1", "", "", "", ""],
        # visible_ids: pair_one + pair_three (pair_two unchecked → hidden)
        "visible_ids": [str(pair_one.id), str(pair_three.id)],
    }
    response = operator.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/save",
        data=payload,
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(pair_one)
    db.refresh(pair_two)
    db.refresh(pair_three)
    assert pair_one.label == "P1"
    assert pair_one.visible is True
    assert pair_two.visible is False
    assert pair_three.visible is True

    # Reviewer surface should render P1 header for pair_one, omit pair_two,
    # show pair_three with default label.
    _activate(operator, db, review_session.id)
    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(
        f"/reviewer/sessions/{review_session.id}"
    ).text
    assert "<th>P1</th>" in body
    assert "<th>Pair context 2</th>" not in body
    assert "<th>Pair context 3</th>" in body

    saved_event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.display_fields_saved",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(saved_event) == 1
