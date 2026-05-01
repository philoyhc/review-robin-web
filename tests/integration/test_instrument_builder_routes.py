"""Integration tests for the consolidated /instruments builder (Segment 10A)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import session_lifecycle as lifecycle


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid",
        email="r@example.edu",
        name="R Reviewer",
        provider="aad",
    )


def _make_session(
    client: TestClient, db: Session, *, code: str = "seg10a"
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


def _instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_instruments_index_renders_settings_and_per_instrument_card(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="card-1")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Header card now folds the deadline + accepting + visibility status
    # into the same card as the setup nav (per the rebuild spec at
    # guide/instruments.md). Verify the status content rendered.
    assert "Session deadline (auto-close):" in body
    assert "Visibility when closed:" in body
    assert "Status:" in body
    instrument = _instrument(db, review_session.id)  # noqa: F841
    assert ">Instrument #1</h2>" in body


def test_legacy_per_instrument_get_redirects_to_consolidated(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="redir-1")
    instrument = _instrument(db, review_session.id)
    response = client.get(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{review_session.id}/instruments"
    )


def test_edit_description_redirects_and_invalidates(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="desc-1")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    db.refresh(review_session)
    assert review_session.status == "validated"

    instrument = _instrument(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/edit",
        data={"description": "Spring 2026 Peer Review"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.status == "draft"
    db.refresh(instrument)
    assert instrument.description == "Spring 2026 Peer Review"

    invalidated = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.invalidated",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(invalidated) >= 1


def test_add_field_auto_slugifies_blank_field_key(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="add-slug")
    instrument = _instrument(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields",
        data={
            "field_key": "",
            "label": "Decision Point",
            "response_type": "yes_no",
            "help_text_visible": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.label == "Decision Point",
        )
    ).scalar_one()
    assert field.field_key == "decision_point"


def test_edit_field_required_warning_redirects_with_query(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="warn-edit")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)

    instrument = _instrument(db, review_session.id)
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{comments.id}/edit",
        data={
            "label": "Comments",
            "required": "true",
            "help_text_visible": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "required_warning=" in location
    assert f"field_id={comments.id}" in location


def test_delete_field_with_responses_blocks_then_confirms(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="del-cascade")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)

    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().first()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="3",
        )
    )
    db.flush()

    blocked = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{rating.id}/delete",
        data={},
        follow_redirects=False,
    )
    assert blocked.status_code == 303
    assert "delete_blocked_field_id=" in blocked.headers["location"]
    still_present = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.id == rating.id
        )
    ).scalar_one_or_none()
    assert still_present is not None

    confirmed = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{rating.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303
    gone = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.id == rating.id
        )
    ).scalar_one_or_none()
    assert gone is None


def test_move_field_repacks_orders(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="move-r")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{rating.id}/move",
        data={"direction": "down"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    fields = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .order_by(InstrumentResponseField.order)
    ).scalars().all()
    assert [f.field_key for f in fields] == ["comments", "rating"]
    assert [f.order for f in fields] == [0, 1]


def test_bulk_accepting_all_off_writes_single_audit_no_invalidate(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bulk-r")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/accepting/all-off",
        follow_redirects=False,
    )
    assert response.status_code == 303

    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().all()
    assert all(not i.accepting_responses for i in instruments)

    bulk_events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instruments.bulk_accepting_responses",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(bulk_events) == 1

    db.refresh(review_session)
    assert review_session.status == "ready"  # bulk does not invalidate


def test_locked_when_ready_returns_409_for_mutations(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="locked-1")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"

    instrument = _instrument(db, review_session.id)

    desc = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/edit",
        data={"description": "x"},
        follow_redirects=False,
    )
    assert desc.status_code == 409

    add = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields",
        data={"label": "X", "response_type": "short_text"},
        follow_redirects=False,
    )
    assert add.status_code == 409

    bulk = client.post(
        f"/operator/sessions/{review_session.id}/instruments/accepting/all-off",
        follow_redirects=False,
    )
    assert bulk.status_code == 303  # bulk-accepting allowed in ready


def test_reviewer_surface_shows_help_block_only_for_visible_help_text(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="rev-help")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)

    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.help_text = "Score 1 (poor) to 5 (excellent)."
    rating.help_text_visible = True
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()
    comments.help_text = "Hidden tip."
    comments.help_text_visible = False
    db.flush()

    _activate(operator, db, review_session.id)

    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert "Score 1 (poor) to 5 (excellent)." in body
    assert "Hidden tip." not in body


def test_reviewer_surface_uses_instrument_description_when_set(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="rev-desc")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)

    instrument = _instrument(db, review_session.id)
    instrument.description = "Spring Peer Review"
    db.flush()
    _activate(operator, db, review_session.id)

    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert ">Spring Peer Review<" in body


def test_reviewer_surface_renders_yes_no_field_added_via_route(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="rev-add")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)

    instrument = _instrument(db, review_session.id)
    response = operator.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields",
        data={
            "field_key": "decision",
            "label": "Decision",
            "response_type": "yes_no",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    _activate(operator, db, review_session.id)
    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(f"/reviewer/sessions/{review_session.id}").text
    assert "Decision" in body
    assert 'name="response[' in body
    assert "][decision]" in body


def test_activation_blocked_when_instrument_has_no_response_fields(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="empty-instr-route")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)

    instrument = _instrument(db, review_session.id)
    fields = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).scalars().all()
    for field in fields:
        client.post(
            f"/operator/sessions/{review_session.id}/instruments"
            f"/{instrument.id}/fields/{field.id}/delete",
            data={"confirm": "true"},
            follow_redirects=False,
        )

    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    db.refresh(review_session)
    assert review_session.status != "validated"

    activate = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert activate.status_code == 400
