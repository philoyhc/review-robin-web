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
    SessionRuleSet,
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


def test_add_new_model_creates_instrument_with_is_new_model_flag(
    client: TestClient, db: Session
) -> None:
    """The +New model button posts to /instruments/add-new-model, which
    creates a real instrument with ``is_new_model=True`` slotted
    immediately after the source. Concept-test affordance for the
    Instrument Builder vertical-bands card."""
    review_session = _make_session(client, db, code="add-new-model")
    source = _instrument(db, review_session.id)

    resp = client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    assert new_model.is_new_model is True
    assert new_model.order == source.order + 1
    db.refresh(source)
    assert source.is_new_model is False

    # New-model card renders with the bands placeholder and the
    # New model status pill on the identity card.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Pool of reviewers" in body  # Band 1 Link 1 column
    assert "Pool of those reviewed" in body  # Band 1 Link 2 column
    assert "Unit of review" in body  # Band 1 Link 3 column
    assert "Review Instrument" in body  # Band 2 heading
    assert "Visibility" in body  # Band 3 left-column table title
    assert ">New model<" in body  # status pill on the new-model card

    # Delete on the new-model card uses the standard delete route
    # (no special new-model-only path) and works end-to-end.
    new_model_id = new_model.id
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model_id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert (
        db.execute(select(Instrument).where(Instrument.id == new_model_id))
        .scalar_one_or_none()
        is None
    )


def _seed_tag_data(db: Session, session_id: int) -> tuple[int, int]:
    """Seed one reviewer + one reviewee with populated tag_1 values so
    the new-model Band 1 dropdowns have usable tag options. Returns
    ``(reviewer_id, reviewee_id)``."""
    reviewer = Reviewer(
        session_id=session_id,
        name="R1",
        email="r1@example.edu",
        tag_1="Lead",
    )
    reviewee = Reviewee(
        session_id=session_id,
        name="E1",
        email_or_identifier="e1@example.edu",
        tag_1="Team A",
    )
    db.add_all([reviewer, reviewee])
    db.commit()
    return reviewer.id, reviewee.id


def test_new_model_band1_persists_link1_link2_link3_round_trip(
    client: TestClient, db: Session
) -> None:
    """End-to-end Band 1 wiring: edit a new-model card with Link 1
    rules, Link 2 rules, and Link 3 grouped + boundary tag; POST the
    bulk-save form; reload and assert each Link rehydrates exactly."""
    review_session = _make_session(client, db, code="nm-band1")
    _seed_tag_data(db, review_session.id)

    # Add a new-model instrument after the default one.
    source = _instrument(db, review_session.id)
    resp = client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # POST Band 1: Link 1 in Filter mode with one rule
    # (reviewer.tag1 IS "Lead"), Link 2 in Filter mode with one
    # cross-side rule (reviewee.tag1 IS THE SAME AS reviewer.tag1),
    # and Link 3 grouped on reviewee.tag1.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "filter",
            "link1_combinator": "AND",
            "link1_field": "reviewer.tag1",
            "link1_op": "IS",
            "link1_operand_value": "Lead",
            "link1_operand_tag": "",
            "link2_mode": "filter",
            "link2_combinator": "OR",
            "link2_field": "reviewee.tag1",
            "link2_op": "IS THE SAME AS",
            "link2_operand_value": "",
            "link2_operand_tag": "reviewer.tag1",
            "link3_mode": "grouped",
            "link3_boundary": "reviewee.tag1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Reload from DB and check storage.
    db.refresh(new_model)
    assert new_model.group_kind == "r1"
    assert new_model.rule_set_id is not None
    rule_set = db.get(SessionRuleSet, new_model.rule_set_id)
    assert rule_set is not None
    # rules_json should carry one Composite per Link.
    by_id = {entry["id"]: entry for entry in rule_set.rules_json}
    assert set(by_id) == {"link1", "link2"}
    assert by_id["link1"]["kind"] == "COMPOSITE"
    assert by_id["link1"]["op"] == "AND"
    assert by_id["link1"]["rules"][0]["predicate"] == {
        "field": "reviewer.tag1",
        "operator": "equals",
        "operand": "Lead",
        "case_sensitive": False,
    }
    assert by_id["link2"]["op"] == "OR"
    assert by_id["link2"]["rules"][0]["predicate"] == {
        "field": "reviewee.tag1",
        "operator": "same_as",
        "operand": "reviewer.tag1",
        "case_sensitive": False,
    }

    # Reload the index and confirm the controls hydrate. We check key
    # markers in the rendered HTML; the JS preserves the chip state
    # client-side from the data-* attrs the template sets.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={new_model.id}"
    ).text
    # Normalise whitespace so multi-line attribute formatting in the
    # template doesn't make the substring checks brittle.
    flat = " ".join(body.split())
    assert 'data-new-model-rule-mode="filter"' in flat
    assert 'data-new-model-unit-mode="group"' in flat
    # The hidden form inputs round-trip the persisted state.
    assert 'name="link1_mode" data-new-model-mode-input value="filter"' in flat
    assert (
        'name="link2_combinator" data-new-model-combinator-input value="OR"'
        in flat
    )
    assert (
        'name="link3_mode" data-new-model-link3-mode-input value="grouped"'
        in flat
    )
    # Link 1's operand value re-renders into its input.
    assert 'value="Lead"' in flat
    # Link 2's tag-operand select marks reviewer.tag1 as the selected option.
    assert '<option value="reviewer.tag1" selected>' in flat


def test_new_model_band1_all_mode_clears_rules(
    client: TestClient, db: Session
) -> None:
    """Switching a Link back to All mode drops its Composite from
    rules_json, and switching Link 3 back to Individual clears
    group_kind to NULL."""
    review_session = _make_session(client, db, code="nm-clear")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Seed state: Filter + Grouped.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "filter",
            "link1_combinator": "AND",
            "link1_field": "reviewer.tag1",
            "link1_op": "IS",
            "link1_operand_value": "Lead",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "grouped",
            "link3_boundary": "reviewee.tag1",
        },
        follow_redirects=False,
    )
    db.refresh(new_model)
    assert new_model.group_kind == "r1"
    rule_set_id = new_model.rule_set_id
    assert rule_set_id is not None

    # Now flip both Links to All and Link 3 to Individual.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "reviewer.tag1",
            "link1_op": "IS",
            "link1_operand_value": "Lead",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "individual",
        },
        follow_redirects=False,
    )
    db.refresh(new_model)
    assert new_model.group_kind is None
    # The SessionRuleSet row stays but its rules_json is now empty.
    rule_set = db.get(SessionRuleSet, rule_set_id)
    assert rule_set is not None
    assert rule_set.rules_json == []


def test_new_model_band2_renders_selectable_pills_with_data_attrs(
    client: TestClient, db: Session
) -> None:
    """Band 2 (Review Instrument) lists every populated display field
    on the new-model instrument as a click-to-select chip, with
    data-* attributes carrying the sample value the client-side
    preview-row builder consumes. Sample data does NOT show inside
    the pill text — pills only show the friendly label."""
    review_session = _make_session(client, db, code="nm-band2")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    # Band heading renamed; the "Sample reviewee:" sub-caption is gone.
    assert "Review Instrument" in flat
    assert ">Band 2<" not in flat
    assert "Sample reviewee:" not in flat
    # Pills are click-to-toggle (role=button) and carry the
    # canonical key + sample value as data attributes for the JS
    # preview builder.
    assert 'data-key="reviewee.name"' in flat
    assert 'data-key="reviewee.email_or_identifier"' in flat
    assert 'data-key="reviewee.tag_1"' in flat
    # Sample values ride on data-value (not inside the pill text).
    assert 'data-value="E1"' in flat
    assert 'data-value="e1@example.edu"' in flat
    assert 'data-value="Team A"' in flat
    # All pills start unselected (aria-pressed=false).
    assert 'aria-pressed="false"' in flat
    # Group-selectability is encoded for the JS unit-mode flip:
    # name + tag_1 selectable in Group; email_or_identifier not.
    assert (
        'data-key="reviewee.name" data-label="Name" data-source-type="reviewee" data-source-field="name" data-value="E1" data-selectable-in-group="true"'
        in flat
    )
    assert (
        'data-key="reviewee.email_or_identifier" data-label="Email" data-source-type="reviewee" data-source-field="email_or_identifier" data-value="e1@example.edu" data-selectable-in-group="false"'
        in flat
    )
    # The sample-names list rides on the Band 2 wrapper for the
    # Group-mode preview's member-name line. With one reviewee, the
    # list is just "E1" and extra count is 0.
    assert 'data-new-model-band2-sample-names="E1"' in flat
    assert 'data-new-model-band2-sample-extra-count="0"' in flat


def test_new_model_band2_handles_session_with_no_reviewees(
    client: TestClient, db: Session
) -> None:
    """When the session has no reviewees with data, Band 2 still
    renders the heading; the pill row collapses to a Setup-page-style
    em-dash placeholder."""
    review_session = _make_session(client, db, code="nm-band2-empty")
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    assert "Review Instrument" in flat
    # Empty-pill-list placeholder lands inside the pill row.
    assert (
        '<div data-new-model-band2-pills style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;"> <span class="muted">—</span>'
        in flat
    )
    # No pills rendered (the data-key attr only appears on pill
    # spans, not on the JS selector matching them).
    assert "data-key=" not in flat
    assert 'data-new-model-band2-sample-names=""' in flat


def test_new_model_band2_column_widths_round_trip(
    client: TestClient, db: Session
) -> None:
    """POSTing column widths to /column-widths persists them on
    instruments.column_widths; reload propagates them onto the pill
    + card data attributes that drive the Band 2 preview's column
    sizing."""
    review_session = _make_session(client, db, code="nm-widths")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    # The tag_1 display field is lazy-seeded on the first index
    # render — visit the page so the field exists by the time we
    # look it up.
    client.get(f"/operator/sessions/{review_session.id}/instruments")
    db.refresh(new_model)
    tag_field = next(
        df
        for df in new_model.display_fields
        if df.source_type == "reviewee" and df.source_field == "tag_1"
    )

    # POST widths: identity at 220px, tag_1 column at 180px.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/column-widths",
        json={
            "widths": {
                "identity": 220,
                f"df_{tag_field.id}": 180,
                "unknown_key": 999,  # dropped silently
                "df_99999": 555,  # dropped — not a real field id
            }
        },
    )
    assert resp.status_code == 200

    db.refresh(new_model)
    assert new_model.column_widths == {
        "identity": 220,
        f"df_{tag_field.id}": 180,
    }

    # Reload the index — widths surface as data attrs the JS reads.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    assert 'data-new-model-band2-identity-width="220"' in flat
    assert f'data-display-field-id="{tag_field.id}" data-width="180"' in flat


def test_new_model_band2_column_widths_clamps_and_clears(
    client: TestClient, db: Session
) -> None:
    """Out-of-range widths clamp to [40, 1200]; an empty widths dict
    clears the column_widths column back to NULL."""
    review_session = _make_session(client, db, code="nm-clamp")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Below-min and above-max get clamped.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/column-widths",
        json={"widths": {"identity": 10, "df_unused": 9999}},
    )
    db.refresh(new_model)
    assert new_model.column_widths == {"identity": 40}

    # Empty dict clears.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/column-widths",
        json={"widths": {}},
    )
    db.refresh(new_model)
    assert new_model.column_widths is None


def test_new_model_band2_display_fields_order_round_trip(
    client: TestClient, db: Session
) -> None:
    """POSTing display-field ids to /display-fields/order persists the
    new sequence onto each row's ``order`` column. Locked Name + Email
    rows stay pinned at orders 0 and 1; the non-locked rows take
    orders 2..N+1 in the order the client requested."""
    review_session = _make_session(client, db, code="nm-order")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    # Trigger the lazy-seed for tag display fields by rendering the
    # page first.
    client.get(f"/operator/sessions/{review_session.id}/instruments")
    db.refresh(new_model)
    by_source = {
        f.source_field: f for f in new_model.display_fields
        if f.source_type == "reviewee"
    }
    tag_1 = by_source["tag_1"]
    name = by_source["name"]
    email = by_source["email_or_identifier"]

    # Reorder the unlocked fields — swap tag_1 to first non-locked
    # position. ``ordered_ids`` must enumerate every non-locked
    # display field id exactly once.
    unlocked_ids = [
        f.id for f in new_model.display_fields
        if (f.source_type, f.source_field) not in (("reviewee", "name"), ("reviewee", "email_or_identifier"))
    ]
    new_order = [tag_1.id] + [fid for fid in unlocked_ids if fid != tag_1.id]
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/display-fields/order",
        json={"ordered_ids": new_order},
    )
    assert resp.status_code == 200

    db.refresh(new_model)
    db.refresh(name)
    db.refresh(email)
    db.refresh(tag_1)
    # Locked fields stay at orders 0, 1.
    assert name.order == 0
    assert email.order == 1
    # tag_1 lands at order 2 (first non-locked slot).
    assert tag_1.order == 2


def test_new_model_band2_display_fields_order_rejects_locked_id(
    client: TestClient, db: Session
) -> None:
    """The route refuses an ordered_ids payload that includes a locked
    field id (RevieweeName / RevieweeEmail) or omits a non-locked id."""
    review_session = _make_session(client, db, code="nm-order-bad")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    client.get(f"/operator/sessions/{review_session.id}/instruments")
    db.refresh(new_model)
    name = next(
        f for f in new_model.display_fields
        if f.source_type == "reviewee" and f.source_field == "name"
    )

    # Including the locked Name id should yield a 400.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/display-fields/order",
        json={"ordered_ids": [name.id]},
    )
    assert resp.status_code == 400

    # Empty list (missing non-locked ids) is also rejected.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/display-fields/order",
        json={"ordered_ids": []},
    )
    assert resp.status_code == 400


def test_new_model_band2_state_round_trip(
    client: TestClient, db: Session
) -> None:
    """POSTing band2-state persists the operator's selected display
    pills + response-field rows; reload renders pills with the
    selected aria-pressed state, the divider, and the Band 3 rows
    pre-populated."""
    review_session = _make_session(client, db, code="nm-band2-state")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": [
                "reviewee.name",
                "reviewee.email_or_identifier",
                "bogus.unknown",  # dropped silently
            ],
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "list_options": "",
                    "selected": True,
                },
                {
                    "name": "Comments",
                    "data_type": "string",
                    "min": "",
                    "max": "200",
                    "step": "",
                    "list_options": "",
                    "selected": False,
                },
                # Empty-name entry dropped.
                {"name": " ", "data_type": "string", "selected": True},
            ],
        },
    )
    assert resp.status_code == 200

    db.refresh(new_model)
    assert new_model.band2_state["selected_display_keys"] == [
        "reviewee.name",
        "reviewee.email_or_identifier",
    ]
    rfs = new_model.band2_state["response_fields"]
    assert len(rfs) == 2
    assert rfs[0]["name"] == "Rating"
    assert rfs[0]["data_type"] == "integer"
    assert rfs[0]["min"] == "1"
    assert rfs[0]["max"] == "5"
    assert rfs[0]["step"] == "1"
    assert rfs[0]["selected"] is True
    assert rfs[1]["name"] == "Comments"
    assert rfs[1]["selected"] is False

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    # Selected display pills carry aria-pressed="true".
    assert 'data-key="reviewee.name" data-label="Name" data-source-type="reviewee" data-source-field="name"' in flat
    # The `||` divider lands once response pills are present.
    assert 'data-new-model-band2-pills-divider' in flat
    # Saved response pills + their rows hydrate with the saved labels.
    assert '>Rating</span>' in flat or '⠿</span>Rating</span>' in flat
    assert '>Comments</span>' in flat or '⠿</span>Comments</span>' in flat
    # Band 3 Response field rows are pre-populated with the saved
    # values.
    assert 'value="Rating"' in flat
    assert 'value="Comments"' in flat


def test_new_model_band2_group_preview_partitions_by_boundary_tag(
    client: TestClient, db: Session
) -> None:
    """When the instrument is in Group mode with a reviewee boundary
    tag, the Band 2 preview's sample-names list reflects ONE group
    (the group the sample reviewee belongs to), not the whole
    roster."""
    review_session = _make_session(client, db, code="nm-group-part")
    # Seed three reviewees split across two tag_1 values.
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="a@example.edu",
                tag_1="Alpha",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Bob",
                email_or_identifier="b@example.edu",
                tag_1="Alpha",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="c@example.edu",
                tag_1="Beta",
            ),
        ]
    )
    db.commit()
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Save: Group mode with boundary tag = reviewee.tag_1.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "",
            "link1_op": "",
            "link1_operand_value": "",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "grouped",
            "link3_boundary": "reviewee.tag1",
        },
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())
    # Sample-names attr should hold only the Alpha group (Alice +
    # Bob, sorted alphabetically), NOT Carol.
    assert 'data-new-model-band2-sample-names="Alice|Bob"' in flat
    assert "Carol" not in body.split('data-new-model-band2-sample-names="')[1].split('"')[0]
    # Roster payload rides on the band2 wrapper so the preview JS
    # can re-partition on the fly when the operator picks a new
    # boundary tag client-side (before saving). Uses a single-quoted
    # attribute since tojson doesn't escape `"` and the JSON contains
    # them around every string.
    assert "data-new-model-band2-roster='" in body
    roster_json = body.split("data-new-model-band2-roster='")[1].split("'>")[0]
    assert '"name": "Alice"' in roster_json
    assert "Carol" in roster_json
    # The Link 3 boundary <select> has an onchange handler that
    # triggers a preview rebuild — live Link 3 movement updates the
    # preview without needing to save.
    assert "newModelLink3BoundaryChanged" in body

    # Flip to individual: sample-names goes back to all reviewees.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "",
            "link1_op": "",
            "link1_operand_value": "",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "individual",
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())
    assert 'data-new-model-band2-sample-names="Alice|Bob|Carol"' in flat


def test_new_model_band2_unit_mode_attribute_renders_in_both_modes(
    client: TestClient, db: Session
) -> None:
    """The wrapper's ``data-new-model-band2-unit-mode`` attribute
    reflects the saved group_kind in both edit and view modes — so
    the preview-builder JS picks the correct rendering branch
    regardless of whether the per-instrument Edit gate is open."""
    review_session = _make_session(client, db, code="nm-unit-mode")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Save: Group mode with boundary tag = reviewee.tag_1.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "",
            "link1_op": "",
            "link1_operand_value": "",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "grouped",
            "link3_boundary": "reviewee.tag1",
        },
        follow_redirects=False,
    )

    # View mode (no ?editing=) — the unit-mode attr should still
    # carry "grouped" so the preview JS renders the group cell.
    view_body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'data-new-model-band2-unit-mode="grouped"' in view_body
    # The link3_mode form input only renders as an <input> in edit
    # mode (the attribute name appears in inline JS selectors on
    # every page, hence the more specific check).
    assert '<input ' not in view_body.split(
        'data-new-model-link3-mode-input'
    )[0].rsplit('<', 1)[-1] if 'data-new-model-link3-mode-input' in view_body else True
    assert 'name="link3_mode"' not in view_body

    # Edit mode — wrapper attr still carries the saved mode, and
    # the form input is rendered.
    edit_body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={new_model.id}"
    ).text
    assert 'data-new-model-band2-unit-mode="grouped"' in edit_body
    assert 'name="link3_mode"' in edit_body


def test_new_model_band2_preview_sample_filters_by_link1(
    client: TestClient, db: Session
) -> None:
    """The /preview-sample route runs the rule engine against the
    posted Link 1 + Link 2 form state and returns the first reviewee
    whose pair survives the filter. Without any rules every active
    reviewee is in scope (first by name wins); with a Link 1 rule
    that excludes the first reviewer, the sample reviewee comes from
    a different in-scope reviewer's pool."""
    review_session = _make_session(client, db, code="nm-preview-sample")
    # Two reviewers — one tagged Lead, one tagged Junior — and two
    # reviewees.
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
                tag_1="Lead",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Bob",
                email="bob@example.edu",
                tag_1="Junior",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Eve",
                email_or_identifier="eve@example.edu",
                status="active",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Fay",
                email_or_identifier="fay@example.edu",
                status="active",
            ),
        ]
    )
    db.commit()
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # No rules: first reviewee (alphabetical) wins.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_rules": [],
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_rules": [],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_reviewee"]["name"] == "Eve"

    # Link 1: only Lead reviewers in scope (only Alice). She still
    # has both reviewees in scope, so the first-by-name still wins —
    # Eve. (Different rule would change the answer, but with this
    # filter the picked reviewee should still be a real one.)
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "filter",
            "link1_combinator": "AND",
            "link1_rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_value": "Lead",
                    "operand_tag": "",
                }
            ],
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_rules": [],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_reviewee"]["name"] == "Eve"

    # Link 1: no reviewer is in scope (no one matches the tag). The
    # route returns null instead of throwing.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "filter",
            "link1_combinator": "AND",
            "link1_rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_value": "Nonexistent",
                    "operand_tag": "",
                }
            ],
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_rules": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"sample_reviewee": None}


def test_new_model_band2_refresh_persists_sample_to_band2_state(
    client: TestClient, db: Session
) -> None:
    """Clicking ↻ Refresh preview persists the picked sample
    reviewee on band2_state.sample_reviewee_name so the choice
    survives the next render — operators no longer lose the sample
    when navigating from edit mode to view mode after Save."""
    review_session = _make_session(client, db, code="nm-sample-persist")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
                tag_1="Lead",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Eve",
                email_or_identifier="eve@example.edu",
                status="active",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Fay",
                email_or_identifier="fay@example.edu",
                status="active",
            ),
        ]
    )
    db.commit()
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Refresh fires the preview-sample route; the picked sample is
    # written through to band2_state.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_rules": [],
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_rules": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["sample_reviewee"]["name"] == "Eve"
    db.refresh(new_model)
    assert new_model.band2_state == {"sample_reviewee_name": "Eve"}

    # A subsequent band2_state save (e.g. operator toggles a pill)
    # MUST NOT clobber the sample. set_band2_state preserves the
    # existing sample_reviewee_name when not in the input payload.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": ["reviewee.name"],
            "response_fields": [],
        },
    )
    db.refresh(new_model)
    assert new_model.band2_state["sample_reviewee_name"] == "Eve"
    assert new_model.band2_state["selected_display_keys"] == ["reviewee.name"]

    # View renders the saved sample-name onto the wrapper data-attr
    # — view mode (no ?editing=) carries the saved sample so the
    # preview-builder JS doesn't fall back to "first reviewee by
    # name" on reload.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'data-new-model-band2-sample-name="Eve"' in body


def test_new_model_band2_state_preserves_other_keys_on_partial_writes(
    client: TestClient, db: Session
) -> None:
    """Each top-level band2_state key is independently writable —
    a payload that *omits* a key carries the existing value forward
    rather than wiping it. Regression coverage for the bug where
    clicking ↻ Refresh preview (writes sample_reviewee_name only)
    or toggling a pill (writes selected_display_keys only) clobbered
    the operator's other Band 2 / Band 3 choices."""
    review_session = _make_session(client, db, code="nm-state-preserve")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
                tag_1="Lead",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Eve",
                email_or_identifier="eve@example.edu",
                status="active",
            ),
        ]
    )
    db.commit()
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Seed all three keys via a single full POST.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": ["reviewee.name"],
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "list_options": "",
                    "selected": True,
                }
            ],
            "sample_reviewee_name": "Eve",
        },
    )
    db.refresh(new_model)
    seeded = new_model.band2_state
    assert seeded["selected_display_keys"] == ["reviewee.name"]
    assert len(seeded["response_fields"]) == 1
    assert seeded["sample_reviewee_name"] == "Eve"

    # Pill-toggle write: only selected_display_keys. response_fields
    # + sample_reviewee_name must carry forward.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={"selected_display_keys": ["reviewee.name", "reviewee.email_or_identifier"]},
    )
    db.refresh(new_model)
    assert new_model.band2_state["selected_display_keys"] == [
        "reviewee.name",
        "reviewee.email_or_identifier",
    ]
    assert len(new_model.band2_state["response_fields"]) == 1
    assert new_model.band2_state["sample_reviewee_name"] == "Eve"

    # RF-save write: only response_fields. selected_display_keys +
    # sample_reviewee_name must carry forward.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "list_options": "",
                    "selected": True,
                },
                {
                    "name": "Comments",
                    "data_type": "string",
                    "min": "",
                    "max": "200",
                    "step": "",
                    "list_options": "",
                    "selected": False,
                },
            ]
        },
    )
    db.refresh(new_model)
    assert len(new_model.band2_state["response_fields"]) == 2
    assert new_model.band2_state["selected_display_keys"] == [
        "reviewee.name",
        "reviewee.email_or_identifier",
    ]
    assert new_model.band2_state["sample_reviewee_name"] == "Eve"

    # Refresh-sample write: only sample_reviewee_name (via the
    # preview-sample route which now persists). Both other keys
    # must survive.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_rules": [],
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_rules": [],
        },
    )
    db.refresh(new_model)
    assert new_model.band2_state["sample_reviewee_name"] == "Eve"
    assert new_model.band2_state["selected_display_keys"] == [
        "reviewee.name",
        "reviewee.email_or_identifier",
    ]
    assert len(new_model.band2_state["response_fields"]) == 2


def test_new_model_link3_and_column_widths_survive_form_save(
    client: TestClient, db: Session
) -> None:
    """Repro: column_widths (auto-saved on drag) and group_kind
    (saved via the form Submit) should both survive the form-Save
    POST and re-render with the same values."""
    review_session = _make_session(client, db, code="nm-save-thru")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Simulate a drag-resize: POST column-widths first.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/column-widths",
        json={"widths": {"identity": 220}},
    )
    assert resp.status_code == 200
    db.refresh(new_model)
    assert new_model.column_widths == {"identity": 220}

    # Now simulate the operator clicking Save on the form — POST
    # /fields/save with link3 set to grouped + boundary.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "",
            "link1_op": "",
            "link1_operand_value": "",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "grouped",
            "link3_boundary": "reviewee.tag1",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    # Both must still be there.
    db.refresh(new_model)
    assert new_model.group_kind == "r1", (
        f"Link 3 group_kind cleared by Save (got {new_model.group_kind!r})"
    )
    assert new_model.column_widths == {"identity": 220}, (
        f"column_widths cleared by Save (got {new_model.column_widths!r})"
    )

    # And the re-rendered HTML should reflect both — in view mode
    # AND in edit mode.
    view_body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'data-new-model-band2-identity-width="220"' in view_body
    assert 'data-new-model-band2-unit-mode="grouped"' in view_body
    edit_body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    assert 'data-new-model-band2-identity-width="220"' in edit_body
    assert 'data-new-model-band2-unit-mode="grouped"' in edit_body
    # The Link 3 boundary picker in edit mode should show
    # reviewee.tag1 as the currently selected option (not "—").
    # If this assertion fails, the operator would see the boundary
    # cleared when re-entering edit mode after Save.
    assert (
        '<option value="reviewee.tag1" selected>' in edit_body
    ), (
        "Link 3 boundary picker lost its reviewee.tag1 selection "
        "after Save → reload → re-edit. Re-edit body excerpt:\n"
        + edit_body[
            edit_body.find("data-new-model-unit-cell") : edit_body.find(
                "data-new-model-unit-cell"
            )
            + 1200
        ]
    )


def test_new_model_band2_view_mode_saved_boundary_drives_partition(
    client: TestClient, db: Session
) -> None:
    """View mode (Band 1 inert, link3_boundary <select>s have no
    ``name=`` attr) must still surface the saved boundary fields
    so the preview-builder JS picks the right partition. The
    wrapper carries ``data-new-model-band2-saved-boundary-fields``
    which the JS reads as a fallback in view mode."""
    review_session = _make_session(client, db, code="nm-view-partition")
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="a@example.edu",
                tag_1="Alpha",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Bob",
                email_or_identifier="b@example.edu",
                tag_1="Alpha",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="c@example.edu",
                tag_1="Beta",
            ),
        ]
    )
    db.commit()
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "",
            "link1_op": "",
            "link1_operand_value": "",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "grouped",
            "link3_boundary": "reviewee.tag1",
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'data-new-model-band2-saved-boundary-fields="tag_1"' in body
    assert 'data-new-model-band2-unit-mode="grouped"' in body


def test_new_model_column_widths_snapshot_rides_with_form_save(
    client: TestClient, db: Session
) -> None:
    """Form Save reads the ``column_widths_snapshot`` hidden form
    field and persists the widths in the same transaction —
    eliminates the race where a fast Save click navigates the
    page before the async /column-widths fetch reaches the
    server."""
    review_session = _make_session(client, db, code="nm-widths-form")
    _seed_tag_data(db, review_session.id)
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()

    # Skip the /column-widths POST entirely — simulate the race
    # where the async fetch never made it. Form Save carries the
    # snapshot.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_field": "",
            "link1_op": "",
            "link1_operand_value": "",
            "link1_operand_tag": "",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link2_field": "",
            "link2_op": "",
            "link2_operand_value": "",
            "link2_operand_tag": "",
            "link3_mode": "individual",
            "column_widths_snapshot": '{"identity": 240}',
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    db.refresh(new_model)
    assert new_model.column_widths == {"identity": 240}
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    assert 'name="column_widths_snapshot"' in body
    assert 'data-new-model-band2-identity-width="240"' in body
