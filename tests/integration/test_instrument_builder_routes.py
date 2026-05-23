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
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
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


def _generate_full_matrix(client: TestClient, db: Session, session_id: int) -> None:
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def _activate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}/assignments?validated=1")
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
    # spec/instruments.md). Verify the status content rendered.
    assert "Session deadline (auto-close):" in body
    assert "Visibility when closed:" in body
    instrument = _instrument(db, review_session.id)  # noqa: F841
    assert "Instrument #1" in body


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
    _generate_full_matrix(client, db, review_session.id)
    client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
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
            "response_type": "Yes_no",
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
    _generate_full_matrix(client, db, review_session.id)

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
    _generate_full_matrix(client, db, review_session.id)

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
    _generate_full_matrix(client, db, review_session.id)
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
    _generate_full_matrix(client, db, review_session.id)
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
    _generate_full_matrix(operator, db, review_session.id)

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
    _generate_full_matrix(operator, db, review_session.id)

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
    _generate_full_matrix(operator, db, review_session.id)

    instrument = _instrument(db, review_session.id)
    response = operator.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields",
        data={
            "field_key": "decision",
            "label": "Decision",
            "response_type": "Yes_no",
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
    _generate_full_matrix(client, db, review_session.id)

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

    client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    db.refresh(review_session)
    assert review_session.status != "validated"

    activate = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert activate.status_code == 400


def test_replicate_instrument_clones_content(
    client: TestClient, db: Session
) -> None:
    """Replicate clones an instrument's description, response /
    display fields, group_kind and assignment rows into a new card
    slotted immediately after the source — without the source's
    pinned rule (Segment 13C PR 3)."""
    from app.db.models import (
        AuditEvent,
        InstrumentDisplayField,
        InstrumentResponseField,
    )
    from app.db.models import Assignment as _Assignment

    review_session = _make_session(client, db, code="replicate-1")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, db, review_session.id)
    source = _instrument(db, review_session.id)
    source.description = "Peer review round 1"
    source.group_kind = "r1"
    db.commit()
    source_id = source.id
    source_name = source.name

    def _count(model: object, instrument_id: int) -> int:
        return len(
            db.execute(
                select(model).where(model.instrument_id == instrument_id)
            ).scalars().all()
        )

    src_fields = _count(InstrumentResponseField, source_id)
    src_displays = _count(InstrumentDisplayField, source_id)
    src_assignments = _count(_Assignment, source_id)
    assert src_assignments > 0  # the full matrix was generated

    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{source_id}/replicate",
        follow_redirects=False,
    )
    assert resp.status_code == 303

    copy = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id,
            Instrument.id != source_id,
        )
    ).scalar_one()
    assert copy.name == f"{source_name} (copy)"
    assert copy.description == "Peer review round 1"
    assert copy.group_kind == "r1"
    assert copy.accepting_responses is False
    assert copy.rule_set_id is None
    assert copy.order == db.get(Instrument, source_id).order + 1
    assert _count(InstrumentResponseField, copy.id) == src_fields
    assert _count(InstrumentDisplayField, copy.id) == src_displays
    assert _count(_Assignment, copy.id) == src_assignments

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "instrument.replicated",
        )
    ).scalar_one()
    assert event.detail["refs"]["source_instrument_id"] == source_id
    assert event.detail["refs"]["instrument_id"] == copy.id


def test_add_pilot_creates_instrument_with_is_pilot_flag(
    client: TestClient, db: Session
) -> None:
    """The +Pilot button posts to /instruments/add-pilot, which
    creates a real instrument with ``is_pilot=True`` slotted
    immediately after the source. Concept-test affordance for the
    Instrument Builder vertical-bands card."""
    review_session = _make_session(client, db, code="add-pilot")
    source = _instrument(db, review_session.id)

    resp = client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-pilot",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    pilot = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    assert pilot.is_pilot is True
    assert pilot.order == source.order + 1
    db.refresh(source)
    assert source.is_pilot is False

    # Pilot card renders with the bands placeholder and the
    # Pilot status pill on the identity card.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Pool of reviewers" in body  # Band 1 Link 1 column
    assert "Pool of those reviewed" in body  # Band 1 Link 2 column
    assert "Unit of review" in body  # Band 1 Link 3 column
    assert "Band 2" in body
    assert "Who can see the responses?" in body  # Band 3 Link 4 column
    assert "What can they see?" in body  # Band 3 Link 5 column
    assert "When can they see them?" in body  # Band 3 Link 6 column
    assert ">Pilot<" in body  # status pill on the pilot card

    # Delete on the pilot card uses the standard delete route
    # (no special pilot-only path) and works end-to-end.
    pilot_id = pilot.id
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{pilot_id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert (
        db.execute(select(Instrument).where(Instrument.id == pilot_id))
        .scalar_one_or_none()
        is None
    )
