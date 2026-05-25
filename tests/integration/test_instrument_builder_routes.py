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
    InstrumentDisplayField,
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


def _band2_rfs(instrument: Instrument) -> list[dict]:
    """Wave 3 PR iii test helper — rebuild the legacy
    ``band2_state.response_fields`` JSON shape from
    ``InstrumentResponseField`` rows + ``instrument.column_widths``,
    sorted by order. Lets existing tests that probe the old JSON
    shape keep their assertions with minimal churn after the JSON
    write side retired (decision 5 — DB is now authoritative).
    """
    column_widths = instrument.column_widths or {}
    out: list[dict] = []
    for rf in sorted(instrument.response_fields, key=lambda f: f.order):
        data_type_lower = (rf._inline_data_type or "String").lower()
        entry: dict = {
            "id": rf.id,
            "name": rf.label,
            "data_type": data_type_lower,
            "min": "" if rf._inline_min is None else (
                str(int(rf._inline_min))
                if rf._inline_min == int(rf._inline_min)
                else f"{rf._inline_min:g}"
            ),
            "max": "" if rf._inline_max is None else (
                str(int(rf._inline_max))
                if rf._inline_max == int(rf._inline_max)
                else f"{rf._inline_max:g}"
            ),
            "step": "" if rf._inline_step is None else (
                str(int(rf._inline_step))
                if rf._inline_step == int(rf._inline_step)
                else f"{rf._inline_step:g}"
            ),
            "list_options": rf._inline_list_csv or "",
            "selected": rf.visible,
            "required": rf.required,
            "help_text": rf.help_text or "",
            "help_text_visible": rf.help_text_visible,
        }
        width = column_widths.get(f"rf_{rf.id}")
        if width is not None:
            entry["width_px"] = width
        out.append(entry)
    return out


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
    assert "Preview review instrument" in body  # Band 2 heading
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
    """Band 2 (Preview review instrument) lists every populated display field
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
    assert "Preview review instrument" in flat
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
    """When the session has no reviewees with data and no
    operator-authored response fields, Band 2 still renders the
    heading; the pill row collapses to a Setup-page-style
    em-dash placeholder."""
    review_session = _make_session(client, db, code="nm-band2-empty")
    source = _instrument(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    # Wave 3 PR i (b) contract — band2 view layer surfaces the
    # instrument's InstrumentResponseField rows (including the
    # seeded Rating + Comments defaults from create_instrument)
    # as response chips when band2_state.response_fields is
    # empty. Clear those rows so the "no pills" assertion below
    # holds.
    new_model = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id,
            Instrument.is_new_model.is_(True),
        )
    ).scalar_one()
    for rf in list(new_model.response_fields):
        db.delete(rf)
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    assert "Preview review instrument" in flat
    # Empty-pill-list placeholder lands inside the pill row.
    # (The pill row sits at the bottom of Band 2, flush-right, with
    # ``justify-content: flex-end`` and ``margin-top: 16px``.)
    assert (
        '<div data-new-model-band2-pills style="display: flex; flex-wrap: wrap; gap: 8px;'
        in flat
    )
    assert "justify-content: flex-end" in flat
    assert '<span class="muted">—</span>' in flat
    # No Band 2 pills rendered. The selector substrings in the
    # inline JS use ``data-new-model-band2-pill`` and ``data-key=``
    # inside bracket-enclosed CSS selectors, so we look for the
    # unique pill click handler binding instead — it only renders
    # on actual pill spans.
    assert "onclick=\"newModelToggleBand2Pill(this)\"" not in body
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
    rfs = _band2_rfs(new_model)
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
    # Wave 3 PR iii — response fields are DB rows; legacy JSON shape
    # rebuilt via _band2_rfs.
    assert len(_band2_rfs(new_model)) == 1
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
    assert len(_band2_rfs(new_model)) == 1
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
    assert len(_band2_rfs(new_model)) == 2
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
    assert len(_band2_rfs(new_model)) == 2


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


def test_new_model_response_field_width_persists_on_band2_state(
    client: TestClient, db: Session
) -> None:
    """Response-column widths ride on the band2_state response_fields
    entry (not on instruments.column_widths) so they travel with the
    field through drag-reorder. set_band2_state sanitises width_px
    per entry (clamped 40-1200); the template renders it as
    data-width on the response pill."""
    review_session = _make_session(client, db, code="nm-rf-width")
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

    # Persist a response field with a drag-resized width.
    resp = client.post(
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
                    "width_px": 260,
                }
            ]
        },
    )
    assert resp.status_code == 200
    db.refresh(new_model)
    rfs = _band2_rfs(new_model)
    assert rfs[0]["width_px"] == 260

    # Out-of-range widths clamp on store.
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
                    "width_px": 9999,
                }
            ]
        },
    )
    db.refresh(new_model)
    assert _band2_rfs(new_model)[0]["width_px"] == 1200

    # Template renders the stored width as data-width on the
    # response pill — the preview-builder JS picks it up to set
    # the response column's <col style="width: Npx">.
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    assert 'data-source-type="response"' in body
    # The data-width attribute on the response pill should carry
    # the saved width.
    flat = " ".join(body.split())
    assert 'data-row-key="rf_0" data-response-key="rf_0"' in flat
    assert 'data-width="1200"' in flat


# --------------------------------------------------------------------------- #
# Segment 18J Wave 1 PR α — Rec A (conditional skip) + Rec D1 (single roster)
# --------------------------------------------------------------------------- #


def _all_new_model_session(
    client: TestClient, db: Session, *, code: str, n_extra: int = 0
) -> tuple[ReviewSession, list[Instrument]]:
    """Build a session whose instruments are all new-model. Returns
    the session and its instruments. ``n_extra`` adds further
    new-model instruments via the +New model route."""
    review_session = _make_session(client, db, code=code)
    _populate_rosters(client, review_session.id)
    seed = _instrument(db, review_session.id)
    # Convert the seeded instrument to new-model in place rather than
    # adding then deleting it — keeps the test setup minimal.
    seed.is_new_model = True
    db.commit()
    for _ in range(n_extra):
        resp = client.post(
            f"/operator/sessions/{review_session.id}/instruments/add-new-model",
            data={"after": str(seed.id)},
            follow_redirects=False,
        )
        assert resp.status_code == 303
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    return review_session, instruments


def test_rec_a_skips_eligibility_engine_for_all_new_model_page(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rec A — when every instrument on the Instruments index is
    new-model, ``evaluate_session_rule_eligibility`` and
    ``evaluate_instrument_group_pair_counts`` are never called: the
    new-model card renders its rule editor inline and does not use
    the legacy assignment-rule-picker card."""
    review_session, _ = _all_new_model_session(
        client, db, code="rec-a-skip"
    )

    from app.services.rules import session_library

    elig_calls = 0
    group_calls = 0
    real_elig = session_library.evaluate_session_rule_eligibility
    real_group = session_library.evaluate_instrument_group_pair_counts

    def spy_elig(*a, **kw):
        nonlocal elig_calls
        elig_calls += 1
        return real_elig(*a, **kw)

    def spy_group(*a, **kw):
        nonlocal group_calls
        group_calls += 1
        return real_group(*a, **kw)

    monkeypatch.setattr(
        session_library, "evaluate_session_rule_eligibility", spy_elig
    )
    monkeypatch.setattr(
        session_library,
        "evaluate_instrument_group_pair_counts",
        spy_group,
    )
    # Patch the names where views imports them too.
    from app.web.views import _instruments as views_instruments

    if hasattr(views_instruments, "session_library"):
        monkeypatch.setattr(
            views_instruments.session_library,
            "evaluate_session_rule_eligibility",
            spy_elig,
            raising=False,
        )
        monkeypatch.setattr(
            views_instruments.session_library,
            "evaluate_instrument_group_pair_counts",
            spy_group,
            raising=False,
        )

    resp = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    assert resp.status_code == 200
    assert elig_calls == 0
    assert group_calls == 0


def test_rec_a_runs_eligibility_engine_when_legacy_card_present(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rec A's flip side — a page with at least one legacy
    (non-new-model) instrument still pays the eligibility cost.
    Conditional skip is scoped to new-model-only pages."""
    review_session = _make_session(client, db, code="rec-a-legacy")
    _populate_rosters(client, review_session.id)
    # Seeded instrument stays legacy; add a new-model one alongside.
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(_instrument(db, review_session.id).id)},
        follow_redirects=False,
    )

    from app.services.rules import session_library

    elig_calls = 0
    real_elig = session_library.evaluate_session_rule_eligibility

    def spy_elig(*a, **kw):
        nonlocal elig_calls
        elig_calls += 1
        return real_elig(*a, **kw)

    monkeypatch.setattr(
        session_library, "evaluate_session_rule_eligibility", spy_elig
    )
    resp = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    assert resp.status_code == 200
    assert elig_calls == 1


def test_rec_d1_single_active_reviewees_query_per_render(
    client: TestClient, db: Session
) -> None:
    """Rec D1 — the active-reviewees SELECT runs exactly once per
    page render even when K new-model instruments are on the page.
    Before D1 the call was per-card (O(K) queries)."""
    from sqlalchemy import event

    review_session, instruments = _all_new_model_session(
        client, db, code="rec-d1", n_extra=3
    )
    assert len([i for i in instruments if i.is_new_model]) == 4

    bind = db.get_bind()
    active_reviewee_selects = 0

    def before_cursor_execute(conn, cursor, statement, *_a, **_kw):
        nonlocal active_reviewee_selects
        s = " ".join(statement.split()).lower()
        # Match the _new_model_band2_states_for active-reviewees
        # SELECT: a select against reviewees with both the
        # session_id and status filters in the WHERE.
        if (
            "from reviewees" in s
            and "reviewees.session_id" in s
            and "reviewees.status" in s
        ):
            active_reviewee_selects += 1

    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    try:
        resp = client.get(
            f"/operator/sessions/{review_session.id}/instruments"
        )
    finally:
        event.remove(bind, "before_cursor_execute", before_cursor_execute)

    assert resp.status_code == 200
    # Exactly one shared fetch for the four new-model cards' Band 2
    # state, instead of the pre-D1 O(K) per-card pattern.
    assert active_reviewee_selects == 1


# --------------------------------------------------------------------------- #
# Segment 18J Wave 1 PR ε — Gap 10 (rule-constrained preview group expansion)
# --------------------------------------------------------------------------- #


def _group_band2_session(
    client: TestClient, db: Session, *, code: str
) -> tuple[ReviewSession, Instrument]:
    """Build a session with two Team-A reviewees + two Team-B reviewees
    + two reviewers (one Lead, one Junior), and a new-model instrument
    set to Grouped mode on RevieweeTag1."""
    review_session = _make_session(client, db, code=code)
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
                name="Carol",
                email_or_identifier="carol@example.edu",
                tag_1="Team A",
                tag_2="exclude",
                status="active",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Dan",
                email_or_identifier="dan@example.edu",
                tag_1="Team A",
                tag_2="keep",
                status="active",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Eve",
                email_or_identifier="eve@example.edu",
                tag_1="Team B",
                tag_2="keep",
                status="active",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Fay",
                email_or_identifier="fay@example.edu",
                tag_1="Team B",
                tag_2="keep",
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
    # Grouped by RevieweeTag1 (encoded ``r1``).
    new_model.group_kind = "r1"
    db.commit()
    return review_session, new_model


def test_gap_10_preview_route_returns_rule_surviving_group_member_ids(
    client: TestClient, db: Session
) -> None:
    """Gap 10 — the Refresh route now persists the rule-surviving
    reviewee IDs for the sample's boundary key on
    ``band2_state.sample_group_member_ids``. With Links 1+2 narrow
    enough to exclude part of the sample's group, the persisted ID
    set must reflect only the surviving members."""
    review_session, new_model = _group_band2_session(
        client, db, code="gap-10-route"
    )
    # Link 1: only Lead reviewers (Alice). Both Team A reviewees are
    # still in scope under Alice, so both Carol + Dan should appear
    # in the surviving member ID set.
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
    db.refresh(new_model)
    sample_name = new_model.band2_state["sample_reviewee_name"]
    member_ids = new_model.band2_state["sample_group_member_ids"]
    # Sample is one of the Team A pair (alphabetically Carol first
    # within Team A); both Team A reviewees in the ID set.
    by_name = {
        r.name: r.id
        for r in db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    }
    assert sample_name in {"Carol", "Dan"}
    assert sorted(member_ids) == sorted([by_name["Carol"], by_name["Dan"]])

    # Now narrow Link 2 to exclude Carol (filter reviewee by name).
    # Only Dan should survive in Team A.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_rules": [],
            "link2_mode": "filter",
            "link2_combinator": "AND",
            "link2_rules": [
                {
                    "field": "reviewee.tag2",
                    "op": "IS NOT",
                    "operand_value": "exclude",
                    "operand_tag": "",
                }
            ],
        },
    )
    assert resp.status_code == 200
    db.refresh(new_model)
    sample_name = new_model.band2_state["sample_reviewee_name"]
    member_ids = new_model.band2_state["sample_group_member_ids"]
    # Sample must be Dan (Carol excluded). Member set must be {Dan}
    # — not {Carol, Dan}, which is what the pre-Gap-10 unconstrained
    # boundary partition would have returned.
    assert sample_name == "Dan"
    assert member_ids == [by_name["Dan"]]


def test_gap_10_render_filters_group_members_by_persisted_ids(
    client: TestClient, db: Session
) -> None:
    """Gap 10 — the render path's `sample_names` reflects the
    persisted rule-surviving ID set. After a Refresh under Link 2
    that excludes Carol from Team A, the rendered preview must show
    only Dan in the Team A group's member list — not Carol + Dan."""
    review_session, new_model = _group_band2_session(
        client, db, code="gap-10-render"
    )
    by_name = {
        r.name: r.id
        for r in db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    }
    # Refresh with Link 2 excluding Carol; the sample falls on Dan.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/preview-sample",
        json={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link1_rules": [],
            "link2_mode": "filter",
            "link2_combinator": "AND",
            "link2_rules": [
                {
                    "field": "reviewee.tag2",
                    "op": "IS NOT",
                    "operand_value": "exclude",
                    "operand_tag": "",
                }
            ],
        },
    )
    db.refresh(new_model)
    assert new_model.band2_state["sample_reviewee_name"] == "Dan"
    assert new_model.band2_state["sample_group_member_ids"] == [
        by_name["Dan"]
    ]
    # Render the index page; the data-new-model-band2-sample-names
    # attribute carries the rendered group member name list.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    # Find the sample-names attribute on the new-model band 2 card.
    needle = 'data-new-model-band2-sample-names="'
    idx = flat.find(needle)
    assert idx != -1
    end = flat.find('"', idx + len(needle))
    names = flat[idx + len(needle) : end].split("|") if end > idx else []
    # Member list reflects only the rule-surviving ID set — Dan only.
    assert names == ["Dan"]


def test_gap_10_legacy_band2_state_without_member_ids_falls_back(
    client: TestClient, db: Session
) -> None:
    """Back-compat — band2_state rows that pre-date Gap 10 (no
    ``sample_group_member_ids`` key) still render via the
    unconstrained boundary partition. Render must not crash and the
    member list must equal the boundary-tag partition."""
    review_session, new_model = _group_band2_session(
        client, db, code="gap-10-legacy"
    )
    # Simulate a legacy band2_state: only sample_reviewee_name, no
    # member ID set. Write through the ORM directly so we bypass the
    # set_band2_state sanitiser (which would carry no member IDs
    # forward anyway, but make the intent explicit).
    new_model.band2_state = {"sample_reviewee_name": "Carol"}
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    needle = 'data-new-model-band2-sample-names="'
    idx = flat.find(needle)
    assert idx != -1
    end = flat.find('"', idx + len(needle))
    names = flat[idx + len(needle) : end].split("|") if end > idx else []
    # Legacy fallback: both Team A reviewees show (unconstrained
    # boundary partition), as before Gap 10.
    assert sorted(names) == ["Carol", "Dan"]


# --------------------------------------------------------------------------- #
# Segment 18J Wave 1 PR β — Gap 1 (pill → InstrumentDisplayField.visible)
# --------------------------------------------------------------------------- #


def _new_model_with_tags(
    client: TestClient, db: Session, *, code: str
) -> tuple[ReviewSession, Instrument]:
    """Build a session with reviewees that have populated tag_1 +
    tag_2, then create a new-model instrument. The index GET at
    the end triggers the lazy seed of tag_1 / tag_2
    InstrumentDisplayField rows. Returns the session and the
    new-model instrument."""
    review_session = _make_session(client, db, code=code)
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
                name="Carol",
                email_or_identifier="carol@example.edu",
                tag_1="Team A",
                tag_2="alpha",
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
    # Render the index once so build_instruments_context's lazy
    # seed populates tag_1 / tag_2 InstrumentDisplayField rows.
    client.get(f"/operator/sessions/{review_session.id}/instruments")
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    return review_session, new_model


def _df_by_key(
    db: Session, instrument_id: int
) -> dict[str, InstrumentDisplayField]:
    fields = list(
        db.execute(
            select(InstrumentDisplayField).where(
                InstrumentDisplayField.instrument_id == instrument_id
            )
        ).scalars()
    )
    return {f"{f.source_type}.{f.source_field}": f for f in fields}


def test_gap_1_pill_selection_writes_visible_on_display_fields(
    client: TestClient, db: Session
) -> None:
    """Gap 1 — when set_band2_state receives selected_display_keys,
    InstrumentDisplayField.visible is set True for each pill in the
    set and False for each non-locked field NOT in the set. Locked
    Name / Email stay visible regardless."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-1-write"
    )
    # Sanity: by default all display fields default to visible=True.
    before = _df_by_key(db, new_model.id)
    assert before["reviewee.name"].visible is True
    assert before["reviewee.email_or_identifier"].visible is True
    assert before["reviewee.tag_1"].visible is True
    assert before["reviewee.tag_2"].visible is True

    # Operator selects only name + tag_1 (deselects email + tag_2).
    # Name + email are locked and always stay visible regardless of
    # what the payload says, so the meaningful effect is tag_2 →
    # invisible while tag_1 stays visible.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": [
                "reviewee.name",
                "reviewee.tag_1",
            ]
        },
    )
    assert resp.status_code == 200
    db.expire_all()
    after = _df_by_key(db, new_model.id)
    # Locked rows stay visible no matter what.
    assert after["reviewee.name"].visible is True
    assert after["reviewee.email_or_identifier"].visible is True
    # Non-locked fields reflect the selection.
    assert after["reviewee.tag_1"].visible is True
    assert after["reviewee.tag_2"].visible is False

    # Re-select tag_2; it flips back to visible.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": [
                "reviewee.name",
                "reviewee.tag_1",
                "reviewee.tag_2",
            ]
        },
    )
    assert resp.status_code == 200
    db.expire_all()
    after2 = _df_by_key(db, new_model.id)
    assert after2["reviewee.tag_2"].visible is True


def test_gap_1_empty_selection_hides_all_non_locked_fields(
    client: TestClient, db: Session
) -> None:
    """Gap 1 boundary case — an empty selected_display_keys payload
    means "operator unselected everything"; every non-locked field
    flips to invisible. Locked Name / Email still stay visible."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-1-empty"
    )
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={"selected_display_keys": []},
    )
    assert resp.status_code == 200
    db.expire_all()
    after = _df_by_key(db, new_model.id)
    # Locked stay visible.
    assert after["reviewee.name"].visible is True
    assert after["reviewee.email_or_identifier"].visible is True
    # Non-locked all hidden.
    assert after["reviewee.tag_1"].visible is False
    assert after["reviewee.tag_2"].visible is False


def test_gap_1_omitted_selection_preserves_existing_visibility(
    client: TestClient, db: Session
) -> None:
    """Gap 1 — a payload that omits selected_display_keys (e.g. a
    Refresh-only or response-fields-only save) must not touch
    InstrumentDisplayField.visible. The pill→visible sync only
    fires when the key is in the payload."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-1-omit"
    )
    # First: a payload that DOES include selected_display_keys, to
    # set tag_2 invisible.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={"selected_display_keys": ["reviewee.tag_1"]},
    )
    db.expire_all()
    assert _df_by_key(db, new_model.id)["reviewee.tag_2"].visible is False

    # Second: a payload that OMITS selected_display_keys (a Refresh-
    # only save). tag_2 must stay invisible — not silently flipped
    # back to True.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={"sample_reviewee_name": "Carol"},
    )
    db.expire_all()
    assert _df_by_key(db, new_model.id)["reviewee.tag_2"].visible is False


def test_gap_1_view_derives_pill_selection_from_visible(
    client: TestClient, db: Session
) -> None:
    """Gap 1 read path — the rendered pills' is-selected state
    reflects ``InstrumentDisplayField.visible``, not whatever the
    legacy band2_state.selected_display_keys JSON happens to hold.
    Editing the visible flag directly on the ORM (simulating a
    Gap-7 / future-source change to the field model) shows up on
    the next render's pill."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-1-render"
    )
    # Flip tag_2 invisible directly (bypassing set_band2_state) and
    # leave band2_state.selected_display_keys JSON stale / empty.
    fields = _df_by_key(db, new_model.id)
    fields["reviewee.tag_2"].visible = False
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())
    # The pills are server-rendered with aria-pressed reflecting
    # the visible flag. Find the tag_2 pill and check it's unpressed;
    # tag_1 should still be pressed.
    tag2_marker = 'data-source-field="tag_2"'
    tag2_idx = flat.find(tag2_marker)
    assert tag2_idx != -1
    # Walk back ~200 chars to find the pill's aria-pressed value.
    snippet_start = max(0, tag2_idx - 250)
    tag2_pill = flat[snippet_start:tag2_idx + len(tag2_marker)]
    assert 'aria-pressed="false"' in tag2_pill

    tag1_marker = 'data-source-field="tag_1"'
    tag1_idx = flat.find(tag1_marker)
    assert tag1_idx != -1
    snippet_start = max(0, tag1_idx - 250)
    tag1_pill = flat[snippet_start:tag1_idx + len(tag1_marker)]
    assert 'aria-pressed="true"' in tag1_pill


# --------------------------------------------------------------------------- #
# Segment 18J Wave 1 PR γ — Gap 3 (sort badges on preview table header)
# --------------------------------------------------------------------------- #


def test_gap_3_band2_state_carries_sort_spec(
    client: TestClient, db: Session
) -> None:
    """Gap 3 — the view-layer band2 state exposes the persisted
    sort spec so the template can stamp the data attribute + the
    sort-spec hidden-inputs slot, and the preview-builder JS can
    render badges."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-3-state"
    )
    fields = _df_by_key(db, new_model.id)
    tag1_id = fields["reviewee.tag_1"].id
    tag2_id = fields["reviewee.tag_2"].id
    from app.services import instruments as instruments_service
    from app.db.models import User

    actor = db.execute(select(User).limit(1)).scalar_one()
    instruments_service.set_sort_display_fields(
        db,
        instrument=new_model,
        fields=[(tag1_id, "asc"), (tag2_id, "desc")],
        actor=actor,
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())

    needle = "data-new-model-band2-sort-spec='"
    idx = flat.find(needle)
    assert idx != -1
    end = flat.find("'", idx + len(needle))
    spec_json = flat[idx + len(needle) : end]
    import json as _json

    spec = _json.loads(spec_json)
    assert [(e["display_field_id"], e["dir"]) for e in spec] == [
        (tag1_id, "asc"),
        (tag2_id, "desc"),
    ]

    slot_id = f'id="sort-spec-inputs-{new_model.id}"'
    assert slot_id in flat
    assert (
        flat.count(f'name="sort_display_field_id" value="{tag1_id}"') >= 1
    )
    assert (
        flat.count(f'name="sort_display_field_id" value="{tag2_id}"') >= 1
    )
    assert flat.count('name="sort_dir" value="asc"') >= 1
    assert flat.count('name="sort_dir" value="desc"') >= 1


def test_gap_3_bulk_save_persists_sort_spec_via_existing_form(
    client: TestClient, db: Session
) -> None:
    """Gap 3 — the bulk-save form's sort_display_field_id /
    sort_dir parallel arrays (populated by the existing
    _rebuildSortInputs JS on badge cycle) round-trip through the
    same /fields/save route the legacy card uses."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-3-save"
    )
    fields = _df_by_key(db, new_model.id)
    tag1_id = fields["reviewee.tag_1"].id
    tag2_id = fields["reviewee.tag_2"].id

    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "sort_display_field_id": [str(tag2_id), str(tag1_id)],
            "sort_dir": ["desc", "asc"],
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    # Defensive: assert the redirect didn't carry a sort_save_error
    # (which would mean the spec was rejected, not persisted).
    assert "sort_save_error" not in resp.headers.get("location", ""), (
        resp.headers.get("location")
    )
    db.refresh(new_model)
    assert new_model.sort_display_fields == [
        {"display_field_id": tag2_id, "dir": "desc"},
        {"display_field_id": tag1_id, "dir": "asc"},
    ]


def test_gap_3_no_sort_spec_renders_empty_inputs_slot(
    client: TestClient, db: Session
) -> None:
    """Gap 3 — a fresh new-model card with no sort spec renders the
    sort-spec-inputs slot empty (no hidden inputs) and the
    data-new-model-band2-sort-spec attr as []. Both the JS
    preview-builder + bulk-save form handle the empty case."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-3-empty"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())
    assert "data-new-model-band2-sort-spec='[]'" in flat
    slot_open = flat.find(f'id="sort-spec-inputs-{new_model.id}"')
    assert slot_open != -1
    slot_close = flat.find("</div>", slot_open)
    assert slot_close != -1
    assert "sort_display_field_id" not in flat[slot_open:slot_close]


# --------------------------------------------------------------------------- #
# Segment 18J Wave 1 PR δ — Gap 5 (required-flag checkbox on Band 3 rows)
# --------------------------------------------------------------------------- #
#
# Wave 1 caveat: this flag persists into band2_state JSON but
# reviewer-surface enforcement waits for Wave 3 (Gap 2 bridging
# the JSON rows to real InstrumentResponseField rows).


def test_gap_5_required_round_trips_through_band2_state(
    client: TestClient, db: Session
) -> None:
    """Gap 5 — required: true persists onto
    band2_state.response_fields[i].required when included in the
    /band2-state POST. Round-trip preserves it across no-op and
    edit saves."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-5-roundtrip"
    )
    resp = client.post(
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
                    "required": True,
                }
            ]
        },
    )
    assert resp.status_code == 200
    db.refresh(new_model)
    rfs = _band2_rfs(new_model)
    assert len(rfs) == 1
    assert rfs[0]["required"] is True
    # Edit the row to required=False; the change persists.
    resp = client.post(
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
                    "required": False,
                }
            ]
        },
    )
    assert resp.status_code == 200
    db.refresh(new_model)
    assert _band2_rfs(new_model)[0]["required"] is False


def test_gap_5_required_defaults_false_when_omitted(
    client: TestClient, db: Session
) -> None:
    """Gap 5 — payloads that omit required default to False. Matches
    bool(raw.get("required")) → False for missing keys."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-5-default"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    assert _band2_rfs(new_model)[0]["required"] is False


def test_gap_5_template_renders_checkbox_and_data_required(
    client: TestClient, db: Session
) -> None:
    """Gap 5 template — the Band 3 row's Required toggle button
    presets from rf.required (primary class + data-required="true"
    when required, secondary class + data-required="false" when
    not), and the Band 2 pill's data-required attr reflects the
    same value."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="gap-5-render"
    )
    # Seed a required response field directly through band2-state.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "selected": True,
                    "required": True,
                },
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                    "required": False,
                },
            ]
        },
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())
    # Row 1 (Rating, required=True): the R button carries
    # data-required="true" and renders without the secondary
    # class (so it picks up the default primary .btn styling).
    rating_idx = flat.find('value="Rating"')
    assert rating_idx != -1
    rating_block = flat[rating_idx : rating_idx + 2500]
    assert 'data-new-model-rf-required' in rating_block
    btn_idx = rating_block.find('data-new-model-rf-required')
    btn_block = rating_block[btn_idx : btn_idx + 300]
    assert 'data-required="true"' in btn_block
    # Primary style — no "secondary" modifier on the .btn class.
    btn_open_idx = rating_block.rfind('<button', 0, btn_idx)
    btn_open_tag = rating_block[btn_open_idx : btn_idx]
    assert 'class="btn"' in btn_open_tag

    # Row 2 (Notes, required=False): the R button carries
    # data-required="false" and gets the .btn.secondary class.
    notes_idx = flat.find('value="Notes"')
    assert notes_idx != -1
    notes_block = flat[notes_idx : notes_idx + 2500]
    btn_idx2 = notes_block.find('data-new-model-rf-required')
    assert btn_idx2 != -1
    btn_block2 = notes_block[btn_idx2 : btn_idx2 + 300]
    assert 'data-required="false"' in btn_block2
    btn_open_idx2 = notes_block.rfind('<button', 0, btn_idx2)
    btn_open_tag2 = notes_block[btn_open_idx2 : btn_idx2]
    assert 'class="btn secondary"' in btn_open_tag2

    # Band 2 pill data-required reflects each row.
    assert 'data-required="true"' in flat
    assert 'data-required="false"' in flat


def test_band3_help_text_visible_toggle_persists_and_renders(
    client: TestClient, db: Session
) -> None:
    """Band 3 ≡ button — when the operator toggles help-text
    visibility for a response field row, the flag persists into
    band2_state.response_fields[*].help_text_visible. The template
    presets the row button's primary/secondary style from the
    flag, and the Band 2 pill carries the same flag on
    data-help-visible so the client-side preview rebuild can
    inject the half-width help card above the table."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band3-help-toggle"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "selected": True,
                    "help_text_visible": True,
                },
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                    "help_text_visible": False,
                },
            ]
        },
    )
    db.refresh(new_model)
    rfs = _band2_rfs(new_model)
    assert rfs[0]["help_text_visible"] is True
    assert rfs[1]["help_text_visible"] is False

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())

    # Row 1 (Rating, help_text_visible=True): the ≡ button is
    # primary (.btn, no .secondary modifier) and carries
    # data-help-visible="true".
    rating_idx = flat.find('value="Rating"')
    assert rating_idx != -1
    rating_block = flat[rating_idx : rating_idx + 2500]
    btn_idx = rating_block.find('data-new-model-rf-help-visible')
    assert btn_idx != -1
    btn_block = rating_block[btn_idx : btn_idx + 300]
    assert 'data-help-visible="true"' in btn_block
    btn_open_idx = rating_block.rfind('<button', 0, btn_idx)
    btn_open_tag = rating_block[btn_open_idx : btn_idx]
    assert 'class="btn"' in btn_open_tag

    # Row 2 (Notes, help_text_visible=False): the ≡ button is
    # secondary (.btn.secondary) and carries
    # data-help-visible="false".
    notes_idx = flat.find('value="Notes"')
    assert notes_idx != -1
    notes_block = flat[notes_idx : notes_idx + 2500]
    btn_idx2 = notes_block.find('data-new-model-rf-help-visible')
    assert btn_idx2 != -1
    btn_block2 = notes_block[btn_idx2 : btn_idx2 + 300]
    assert 'data-help-visible="false"' in btn_block2
    btn_open_idx2 = notes_block.rfind('<button', 0, btn_idx2)
    btn_open_tag2 = notes_block[btn_open_idx2 : btn_idx2]
    assert 'class="btn secondary"' in btn_open_tag2

    # Band 2 pill data-help-visible reflects each row.
    assert 'data-help-visible="true"' in flat
    assert 'data-help-visible="false"' in flat


def test_band3_help_text_visible_defaults_to_false_when_omitted(
    client: TestClient, db: Session
) -> None:
    """Payloads that omit help_text_visible default to False —
    matches bool(raw.get("help_text_visible")) for missing keys."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band3-help-default"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    assert (
        _band2_rfs(new_model)[0]["help_text_visible"]
        is False
    )


def test_band3_help_text_body_persists_and_renders_on_pill(
    client: TestClient, db: Session
) -> None:
    """Help-text body persists into
    band2_state.response_fields[*].help_text and the response pill
    carries the value on data-help-text so the operator-surface
    help card (and a JS-driven preview rebuild) can render it
    without a server round-trip."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band3-help-body"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "selected": True,
                    "help_text_visible": True,
                    "help_text": "Rate from 1 (poor) to 5 (great).",
                }
            ]
        },
    )
    db.refresh(new_model)
    assert (
        _band2_rfs(new_model)[0]["help_text"]
        == "Rate from 1 (poor) to 5 (great)."
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    # The Band 2 pill carries the help-text body so the JS preview
    # rebuild can inject it into the help card without re-fetching.
    assert 'data-help-text="Rate from 1 (poor) to 5 (great).' in body


def test_band3_help_text_body_clamped_to_1000_chars(
    client: TestClient, db: Session
) -> None:
    """Help-text body is clamped to 1000 chars server-side as a
    defence-in-depth (the textarea's maxlength already enforces
    the same cap on the client). Wave 3 doc decision E."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band3-help-clamp"
    )
    long_text = "x" * 1500
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                    "help_text_visible": True,
                    "help_text": long_text,
                }
            ]
        },
    )
    db.refresh(new_model)
    stored = _band2_rfs(new_model)[0]["help_text"]
    assert len(stored) == 1000
    assert stored == "x" * 1000


def test_band3_help_text_body_defaults_to_empty_when_omitted(
    client: TestClient, db: Session
) -> None:
    """Payloads that omit help_text default to empty string —
    matches the sanitiser's ``str(...)[:1000] if not None else ""``
    contract."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band3-help-body-default"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    assert _band2_rfs(new_model)[0]["help_text"] == ""


# --------------------------------------------------------------------------- #
# Segment 18J Wave 3 PR i — dual-write band2_state.response_fields JSON
# entries into real InstrumentResponseField rows.
# --------------------------------------------------------------------------- #


def test_wave3_pri_creates_irf_row_for_new_entry(
    client: TestClient, db: Session
) -> None:
    """A response-field JSON entry without ``id`` materialises a
    new InstrumentResponseField row on first save; the JSON gets
    its ``id`` back-filled to the new row's PK so subsequent
    saves id-match instead of creating duplicates."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-create"
    )
    # Drop the seeded defaults so we can see the create cleanly.
    for rf in list(new_model.response_fields):
        db.delete(rf)
    db.commit()

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
                    "selected": True,
                    "required": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    rows = list(new_model.response_fields)
    assert len(rows) == 1
    row = rows[0]
    assert row.label == "Rating"
    assert row.required is True
    assert row.visible is True
    assert row._inline_data_type == "Integer"
    assert row._inline_min == 1.0
    assert row._inline_max == 5.0
    assert row._inline_step == 1.0
    # JSON ``id`` back-filled to the new row's PK.
    assert _band2_rfs(new_model)[0]["id"] == row.id


def test_wave3_pri_id_match_updates_existing_row(
    client: TestClient, db: Session
) -> None:
    """A response-field JSON entry with a matching ``id`` updates
    the existing row in place — no duplicate row is created."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-update"
    )
    for rf in list(new_model.response_fields):
        db.delete(rf)
    db.commit()

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
                    "selected": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    row_id = _band2_rfs(new_model)[0]["id"]

    # Second save — same id, updated label + bounds.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": row_id,
                    "name": "Score",
                    "data_type": "integer",
                    "min": "0",
                    "max": "10",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    rows = list(new_model.response_fields)
    assert len(rows) == 1
    assert rows[0].id == row_id
    assert rows[0].label == "Score"
    assert rows[0]._inline_min == 0.0
    assert rows[0]._inline_max == 10.0


def test_full_flow_r_toggle_then_bottom_save_preserves_state(
    client: TestClient, db: Session
) -> None:
    """End-to-end repro for the operator's report that R toggle
    state reverts after clicking the bottom Save button. Confirms:

    1. POST /band2-state (mimicking the R-toggle JS) persists.
    2. POST /fields/save (the bottom Save form) does NOT clobber
       band2_state.response_fields.
    3. Re-rendering the page shows the persisted R state, not
       the seeded default.

    If this test fails, there's a server-side regression. If it
    passes, the bug the operator's seeing is client-side
    (cache, fetch abort, JS error)."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="full-flow-r-save"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    comments = next(
        rf for rf in new_model.response_fields if rf.label == "Comments"
    )

    # Step 1 — simulate R-toggle saveBand2State (Rating's required
    # flipped from True to False, Comments unchanged).
    band2_resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": [],
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "required": False,
                },
                {
                    "id": comments.id,
                    "name": "Comments",
                    "data_type": "string",
                    "max": "2000",
                    "selected": True,
                    "required": False,
                },
            ],
        },
    )
    assert band2_resp.status_code == 200
    db.expire_all()
    new_model = db.get(type(new_model), new_model.id)
    rating_row = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    assert rating_row.required is False
    assert _band2_rfs(new_model)[0]["required"] is False

    # Step 2 — simulate the bottom Save (POST /fields/save with
    # the dfsave form payload — Band 1 + sort spec). This MUST
    # NOT clobber band2_state.response_fields.
    save_resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link3_mode": "individual",
        },
        follow_redirects=False,
    )
    # 303 redirect on success.
    assert save_resp.status_code in (200, 303)
    db.expire_all()
    new_model = db.get(type(new_model), new_model.id)

    # Step 3 — Wave 3 PR iii: response-field state lives on DB rows,
    # not in band2_state JSON. The DB row's required must still be
    # False; the seeded default has NOT crept back in.
    rating_row = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    assert rating_row.required is False, (
        "Bottom Save reverted Rating.required back to seeded default"
    )
    rating_view = next(
        r for r in _band2_rfs(new_model)
        if r.get("id") == rating_row.id
    )
    assert rating_view["required"] is False


def test_full_flow_add_new_response_field_persists_through_save(
    client: TestClient, db: Session
) -> None:
    """End-to-end repro for the operator's report that newly-added
    response fields don't persist through the bottom Save. Same
    structure as the R-toggle test — POST a saveBand2State with a
    new field alongside the seeded rows, then POST the bottom Save,
    then verify the new field is still there."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="full-flow-new-rf"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    comments = next(
        rf for rf in new_model.response_fields if rf.label == "Comments"
    )

    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": [],
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "required": True,
                },
                {
                    "id": comments.id,
                    "name": "Comments",
                    "data_type": "string",
                    "max": "2000",
                    "selected": True,
                    "required": False,
                },
                {
                    "name": "Bonus",  # no id — new entry
                    "data_type": "integer",
                    "min": "0",
                    "max": "100",
                    "step": "1",
                    "selected": True,
                    "required": False,
                },
            ],
        },
    )
    db.expire_all()
    new_model = db.get(type(new_model), new_model.id)
    labels = {rf.label for rf in new_model.response_fields}
    assert "Bonus" in labels

    # Bottom Save — must not clobber the new field.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/fields/save",
        data={
            "link1_mode": "all",
            "link1_combinator": "AND",
            "link2_mode": "all",
            "link2_combinator": "AND",
            "link3_mode": "individual",
        },
        follow_redirects=False,
    )
    db.expire_all()
    new_model = db.get(type(new_model), new_model.id)
    labels = {rf.label for rf in new_model.response_fields}
    assert "Bonus" in labels, (
        "Bottom Save removed the operator-added Bonus row"
    )
    # Wave 3 PR iii — the legacy JSON-shape view (rebuilt from DB
    # rows) also shows Bonus.
    view_labels = {r["name"] for r in _band2_rfs(new_model)}
    assert "Bonus" in view_labels


def test_r_toggle_persists_required_flag_via_dual_write(
    client: TestClient, db: Session
) -> None:
    """Reproduction for the operator-reported "R doesn't persist"
    bug. Simulates the R-toggle saveBand2State payload (which
    keeps every existing pill, with the toggled row's
    ``required`` flipped) and confirms the dual-write helper
    writes through to InstrumentResponseField.required AND
    preserves the flag in band2_state JSON across reload."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="r-toggle-persist"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    comments = next(
        rf for rf in new_model.response_fields if rf.label == "Comments"
    )
    # Seeded defaults: Rating is required=True, Comments is required=False.
    assert rating.required is True
    assert comments.required is False

    # Simulate the R toggle on Rating (off) + saveBand2State.
    # JS payload keeps Comments untouched and flips Rating's
    # required flag.
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": [],
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "required": False,
                },
                {
                    "id": comments.id,
                    "name": "Comments",
                    "data_type": "string",
                    "max": "2000",
                    "selected": True,
                    "required": False,
                },
            ],
        },
    )
    assert response.status_code == 200

    db.expire_all()
    new_model = db.get(type(new_model), new_model.id)
    by_label = {rf.label: rf for rf in new_model.response_fields}
    # Rating.required should now be False.
    assert by_label["Rating"].required is False
    assert by_label["Comments"].required is False
    # band2_state.response_fields JSON also carries the new
    # required flag — used by the template's initial render
    # to set the R button's primary/secondary class.
    json_by_id = {
        r["id"]: r for r in _band2_rfs(new_model)
    }
    assert json_by_id[rating.id]["required"] is False
    assert json_by_id[comments.id]["required"] is False


def test_wave3_pri_pill_selected_flows_through_to_visible_column(
    client: TestClient, db: Session
) -> None:
    """The Band 2 response-pill ``selected`` flag flows through
    to ``InstrumentResponseField.visible`` — mirrors Gap 1's
    display-pill → ``InstrumentDisplayField.visible`` wiring."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-visible"
    )
    for rf in list(new_model.response_fields):
        db.delete(rf)
    db.commit()

    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Notes",
                    "data_type": "string",
                    "max": "2000",
                    "selected": False,
                }
            ]
        },
    )
    db.refresh(new_model)
    rows = list(new_model.response_fields)
    assert len(rows) == 1
    assert rows[0].visible is False


def test_wave3_pri_deletes_unreferenced_row_without_responses(
    client: TestClient, db: Session
) -> None:
    """Posting a JSON payload that omits an existing row's id
    deletes the row (no attached Response rows)."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-delete"
    )
    for rf in list(new_model.response_fields):
        db.delete(rf)
    db.commit()

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
                    "selected": True,
                },
                {
                    "name": "Notes",
                    "data_type": "string",
                    "max": "2000",
                    "selected": True,
                },
            ]
        },
    )
    db.refresh(new_model)
    rating_id = _band2_rfs(new_model)[0]["id"]
    notes_id = _band2_rfs(new_model)[1]["id"]
    assert len(list(new_model.response_fields)) == 2

    # Second save — drop Notes by id.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating_id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )
    db.refresh(new_model)
    remaining_ids = {rf.id for rf in new_model.response_fields}
    assert rating_id in remaining_ids
    assert notes_id not in remaining_ids


def test_wave3_pri_b_contract_populates_band3_from_db(
    client: TestClient, db: Session
) -> None:
    """(b) contract — when band2_state.response_fields is empty,
    the band2 view-layer populates response_fields from the
    instrument's seeded DB rows so Band 3 renders them and the
    next save round-trips ids back through the JSON."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-b-contract"
    )
    # Fresh instrument with seeded Rating + Comments rows;
    # band2_state has no response_fields yet.
    assert new_model.band2_state is None or "response_fields" not in (
        new_model.band2_state or {}
    )
    seeded_rows = {rf.label: rf.id for rf in new_model.response_fields}
    assert "Rating" in seeded_rows
    assert "Comments" in seeded_rows

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    # Band 3 rows render with the seeded rows' ids on the row
    # element (data-rf-id).
    for rf_id in seeded_rows.values():
        assert f'data-rf-id="{rf_id}"' in body


def test_wave3_pri_disabled_x_when_responses_present(
    client: TestClient, db: Session
) -> None:
    """When a response field has attached Response rows, the
    Band 3 X button renders ``disabled`` (no onclick) so the
    operator can't trigger a cascade delete from the UI."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-disabled-x"
    )
    # The seeded "Rating" row will get a Response attached.
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    # Create an assignment + a response for that field.
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().first()
    assert reviewer is not None and reviewee is not None
    assignment = Assignment(
        session_id=review_session.id,
        instrument_id=new_model.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="4",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    # The row carries data-has-responses.
    assert f'data-rf-id="{rating.id}"' in body
    assert 'data-has-responses="true"' in body
    # The X button on the rating row renders disabled (no onclick).
    # Wave 3 PR iii — ``data-rf-id`` now also appears on the response
    # pill, so anchor on the Band 3 row's ``data-new-model-rf-row``
    # combined with the rf-id to find the row uniquely.
    flat = " ".join(body.split())
    row_marker = f'data-new-model-rf-row data-row-key="rf_0" data-rf-id="{rating.id}"'
    rating_row_idx = flat.find(row_marker)
    assert rating_row_idx != -1, "Band 3 row for rating not found"
    rating_block = flat[rating_row_idx : rating_row_idx + 6000]
    x_idx = rating_block.find(">X</button>")
    assert x_idx != -1
    # Walk back to the <button to read its attrs.
    x_open = rating_block.rfind("<button", 0, x_idx)
    x_tag = rating_block[x_open : x_idx]
    assert "disabled" in x_tag
    assert "newModelRfDeleteRow" not in x_tag


def test_wave3_prii_disabled_type_and_bounds_when_responses_present(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR ii — the Band 3 row's data_type select + bound
    inputs render ``disabled`` when the field has saved responses,
    mirroring the X button's existing has_responses gate. The
    operator must clear responses before re-shaping the field;
    server-side ResponseFieldShapeChangeError is the defence-in-
    depth for direct API hits."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-prii-shape-disabled"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().first()
    assignment = Assignment(
        session_id=review_session.id,
        instrument_id=new_model.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="4",
        )
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    # Wave 3 PR iii — ``data-rf-id`` now also rides on the response
    # pill, so anchor on the Band 3 row's combined marker instead.
    flat = " ".join(body.split())
    row_marker = f'data-new-model-rf-row data-row-key="rf_0" data-rf-id="{rating.id}"'
    rating_row_idx = flat.find(row_marker)
    assert rating_row_idx != -1, "Band 3 row for rating not found"
    rating_block = flat[rating_row_idx : rating_row_idx + 6000]
    assert 'data-new-model-rf-shape-locked="true"' in rating_block

    # data_type select disabled.
    sel_idx = rating_block.find("data-new-model-rf-data-type")
    assert sel_idx != -1
    # Slice from the <select that opens this attribute to its closing >.
    sel_open = rating_block.rfind("<select", 0, sel_idx)
    sel_close = rating_block.find(">", sel_idx)
    sel_tag = rating_block[sel_open : sel_close]
    assert "disabled" in sel_tag

    # Each of min / max / step / list bound inputs disabled.
    for bound in ("min", "max", "step", "list"):
        marker = f'data-new-model-rf-bound="{bound}"'
        b_idx = rating_block.find(marker)
        assert b_idx != -1, f"{bound} input missing from rating row"
        b_open = rating_block.rfind("<input", 0, b_idx)
        b_close = rating_block.find(">", b_idx)
        b_tag = rating_block[b_open : b_close]
        assert "disabled" in b_tag, f"{bound} input not disabled when has_responses"


def test_wave3_prii_no_shape_lock_when_no_responses(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR ii — the shape-lock attributes don't render on a
    fresh row with no responses. The data_type select + bound
    inputs stay editable so the operator can author the field."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-prii-no-lock"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    # Wave 3 PR iii — ``data-rf-id`` now also appears on the response
    # pill, so anchor on the Band 3 row's combined marker.
    flat = " ".join(body.split())
    row_marker = f'data-new-model-rf-row data-row-key="rf_0" data-rf-id="{rating.id}"'
    rating_row_idx = flat.find(row_marker)
    assert rating_row_idx != -1, "Band 3 row for rating not found"
    rating_block = flat[rating_row_idx : rating_row_idx + 6000]
    assert 'data-new-model-rf-shape-locked' not in rating_block
    # data_type select is editable.
    sel_idx = rating_block.find("data-new-model-rf-data-type")
    sel_open = rating_block.rfind("<select", 0, sel_idx)
    sel_close = rating_block.find(">", sel_idx)
    sel_tag = rating_block[sel_open : sel_close]
    assert "disabled" not in sel_tag


def test_wave3_pri_cascade_blocked_delete_returns_409(
    client: TestClient, db: Session
) -> None:
    """Defence-in-depth — even when the X button is disabled in
    the UI, a JSON payload that omits a previously-tracked row id
    whose row has attached Response rows gets rejected with 409.
    The dual-write only acts on previously-tracked ids, so seeded
    rows that have never been in JSON are spared; to exercise the
    delete-with-cascade path we first round-trip the row's id
    into JSON, then attach a Response, then POST a payload that
    omits the id."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-cascade-409"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    # First save — round-trip Rating's id into the JSON so a
    # subsequent omitting save lands in the delete branch.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )

    # Attach a Response to the rating row.
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().first()
    assignment = Assignment(
        session_id=review_session.id,
        instrument_id=new_model.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="4",
        )
    )
    db.commit()

    # POST a payload that omits the rating's id — would otherwise
    # delete the row. The route converts ResponsesPresentError
    # into a 409.
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Just a placeholder",
                    "data_type": "string",
                    "max": "100",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 409


def test_wave3_pri_dual_write_authors_new_response_field(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR i — operator-authored rows persist as real
    ``InstrumentResponseField`` rows alongside the seeded defaults.
    Per the PR iii contract, the incoming payload now carries the
    full id set (the view layer's (b) contract populates the JS
    payload from DB rows on first render), so the seeded rows are
    preserved and the new ``Bonus`` row gets created."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-pri-reviewer-unchanged"
    )
    seeded_rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    seeded_comments = next(
        rf for rf in new_model.response_fields if rf.label == "Comments"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": seeded_rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "required": True,
                },
                {
                    "id": seeded_comments.id,
                    "name": "Comments",
                    "data_type": "string",
                    "max": "2000",
                    "selected": True,
                    "required": False,
                },
                {
                    "name": "Bonus",
                    "data_type": "integer",
                    "min": "0",
                    "max": "100",
                    "step": "1",
                    "selected": True,
                    "required": False,
                },
            ]
        },
    )
    db.refresh(new_model)
    labels = {rf.label for rf in new_model.response_fields}
    assert {"Rating", "Comments", "Bonus"} <= labels





def test_band2_intro_card_renders_short_label_description_and_progress(
    client: TestClient, db: Session
) -> None:
    """Band 2 replicates the reviewer-surface per-instrument intro
    card: short_label / description + progress pills (0 done /
    required + all totals). Pill count source is
    band2_state.response_fields filtered by ``selected``."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-intro"
    )
    # Stamp the instrument with a short_label + description so the
    # heading + subtitle both render.
    new_model.short_label = "Peer Review"
    new_model.description = "Quick sanity check after milestone 1."
    db.commit()

    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Rating",
                    "data_type": "integer",
                    "selected": True,
                    "required": True,
                },
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                    "required": False,
                },
                {
                    "name": "Bonus",
                    "data_type": "integer",
                    "selected": False,
                    "required": True,
                },
            ]
        },
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())

    # Card scaffolding present. Title is "Page #N: <short_label>"
    # (instrument position from the surrounding loop — the
    # helper seeds a source instrument first, so the new model is
    # the 2nd instrument).
    assert "data-new-model-band2-intro-card" in flat
    intro_idx = flat.find("data-new-model-band2-intro-card")
    intro_block = flat[intro_idx : intro_idx + 4000]
    assert "Page #2:" in intro_block
    # short_label renders inside the view span (alongside the
    # Page # prefix); description renders inside the view paragraph.
    assert (
        '<span data-intro-short-label-view style="font-weight: inherit;">Peer Review</span>'
        in intro_block
    )
    assert "Quick sanity check after milestone 1." in intro_block

    # Counts reflect the full authored response-field set, not
    # just the chips currently toggled on in the preview. All 3
    # fields contribute to "All items"; the 2 marked
    # ``required=True`` (Rating + Bonus) contribute to "Required".
    assert "Required items completed: 0/<span data-new-model-intro-required-count>2</span>" in flat
    assert "All items completed: 0/<span data-new-model-intro-all-count>3</span>" in flat
    # Required pill is warning (2 required, 0 done). All pill is
    # neutral count.
    assert 'class="pill pill-warning"' in intro_block
    assert 'class="pill pill-count"' in intro_block


def test_band2_intro_card_omits_progress_when_no_selected_response_fields(
    client: TestClient, db: Session
) -> None:
    """When zero response fields exist on the instrument (no
    operator-authored entries AND seeded defaults cleared), the
    progress-pill row is omitted (matches the reviewer surface's
    "no completion data → no pills" contract)."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-intro-no-rfs"
    )
    new_model.short_label = "Reflection"
    new_model.description = ""
    # Wave 3 PR i (b) contract — band2 view layer surfaces the
    # instrument's InstrumentResponseField rows when band2_state
    # response_fields is empty. Clear the seeded Rating + Comments
    # defaults so the progress pills truly see "zero" and omit.
    for rf in list(new_model.response_fields):
        db.delete(rf)
    db.commit()

    # No response fields seeded → progress row should not render.
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={"response_fields": []},
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    intro_idx = flat.find("data-new-model-band2-intro-card")
    assert intro_idx != -1
    intro_block = flat[intro_idx : intro_idx + 3000]
    # Heading still renders (Page #2: Reflection — source seed
    # instrument is #1).
    assert "Page #2:" in intro_block
    assert (
        '<span data-intro-short-label-view style="font-weight: inherit;">Reflection</span>'
        in intro_block
    )
    # Progress row is rendered (always present so JS can update
    # counts live without a page reload) but ``hidden`` collapses
    # it when the instrument has zero response fields.
    assert "data-new-model-intro-progress" in intro_block
    progress_idx = intro_block.find("data-new-model-intro-progress")
    progress_tag = intro_block[
        intro_block.rfind("<p", 0, progress_idx) : intro_block.find(">", progress_idx) + 1
    ]
    assert "hidden" in progress_tag


def test_band2_intro_card_marks_required_pill_success_when_no_required_fields(
    client: TestClient, db: Session
) -> None:
    """When the operator selects response fields but none are
    required, the Required pill renders as pill-success (vacuously
    complete) instead of pill-warning."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-intro-no-required"
    )
    new_model.short_label = "Notes"
    db.commit()

    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Notes",
                    "data_type": "string",
                    "selected": True,
                    "required": False,
                }
            ]
        },
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())
    assert "Required items completed: 0/<span data-new-model-intro-required-count>0</span>" in flat
    intro_idx = flat.find("data-new-model-band2-intro-card")
    intro_block = flat[intro_idx : intro_idx + 2500]
    assert 'class="pill pill-success"' in intro_block


def test_band2_intro_card_description_textarea_hidden_uses_hidden_attr_only(
    client: TestClient, db: Session
) -> None:
    """Regression: the description textarea must NOT carry an
    explicit ``display`` value in its inline style, otherwise the
    ``hidden`` attribute (which works via the UA stylesheet's
    [hidden] { display: none } rule) gets out-specificity'd by the
    inline style and the textarea remains visible alongside the
    view paragraph in non-edit mode — appearing as a perceivable
    empty box, and doubling up with the view text when JS enters
    edit mode."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-intro-textarea-hidden"
    )
    new_model.short_label = "Hidden Test"
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())
    intro_idx = flat.find("data-new-model-band2-intro-card")
    assert intro_idx != -1
    intro_block = flat[intro_idx : intro_idx + 4000]
    ta_idx = intro_block.find("data-intro-description-input")
    assert ta_idx != -1
    # Walk back to the opening <textarea tag and scan its
    # attributes for an inline display value.
    ta_open = intro_block.rfind("<textarea", 0, ta_idx)
    ta_close = intro_block.find(">", ta_idx)
    ta_tag = intro_block[ta_open : ta_close + 1]
    assert "hidden" in ta_tag
    assert "display:" not in ta_tag.lower()


def test_band2_intro_card_edit_icons_only_render_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    """The intro card's unified ✎/✓ pair (opens / saves both
    short_label + description) only renders when the instrument is
    in edit mode. In view mode (no ``editing=`` query param), the
    icons are absent — operator cannot toggle the inline editor."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-intro-edit-gate"
    )
    new_model.short_label = "Gated"
    new_model.description = "View-mode placeholder."
    db.commit()

    # View mode (no ``editing=...`` param). The JS code that
    # implements the toggle contains the function names so we
    # look for the onclick wiring on the button element.
    view_body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "newModelIntroEdit(this)" not in view_body
    assert "newModelIntroSave(this)" not in view_body

    # Edit mode — unified ✎/✓ pair renders (✓ hidden by default).
    edit_body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={new_model.id}"
    ).text
    assert "newModelIntroEdit(this)" in edit_body
    assert "newModelIntroSave(this)" in edit_body


def test_intro_identity_endpoint_updates_short_label(
    client: TestClient, db: Session
) -> None:
    """POST /identity with {short_label: "..."} updates the
    instrument's short_label and returns 200."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="identity-short-label"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/identity",
        json={"short_label": "Q1 Self-Eval"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    db.refresh(new_model)
    assert new_model.short_label == "Q1 Self-Eval"


def test_intro_identity_endpoint_updates_description(
    client: TestClient, db: Session
) -> None:
    """POST /identity with {description: "..."} updates the
    instrument's description and returns 200."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="identity-description"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/identity",
        json={"description": "Reflect on the milestone."},
    )
    assert response.status_code == 200
    db.refresh(new_model)
    assert new_model.description == "Reflect on the milestone."


def test_intro_identity_endpoint_updates_both_fields(
    client: TestClient, db: Session
) -> None:
    """A single POST can update both fields together."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="identity-both"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/identity",
        json={
            "short_label": "Skills Check",
            "description": "Quarterly skills review.",
        },
    )
    assert response.status_code == 200
    db.refresh(new_model)
    assert new_model.short_label == "Skills Check"
    assert new_model.description == "Quarterly skills review."


def test_intro_identity_endpoint_rejects_short_label_over_32_chars(
    client: TestClient, db: Session
) -> None:
    """short_label > 32 chars is rejected with 400 by the service-side
    cap. UI maxlength enforces the same cap; the endpoint guards
    against bypasses."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="identity-too-long"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/identity",
        json={"short_label": "x" * 33},
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Segment 18J Wave 2 PR i — before_insert listener auto-populates
# inline bound columns from the RTD on new InstrumentResponseField
# rows (additive; backfilled rows already covered in tests/db).
# --------------------------------------------------------------------------- #


def test_wave2_pr_i_listener_inlines_bounds_on_new_response_field(
    client: TestClient, db: Session
) -> None:
    """The before_insert listener on InstrumentResponseField fills
    in the inline bound columns from the row's pointed-at RTD so
    rows created post-migration land in the target shape (not just
    historically-backfilled rows)."""
    from app.db.models import ResponseTypeDefinition, User
    from app.services import instruments as instruments_service

    review_session = _make_session(client, db, code="w2-pri-listener")
    actor = db.execute(select(User).limit(1)).scalar_one()
    # Trigger the lazy RTD seed via the index render.
    client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    rtd_int = db.execute(
        select(ResponseTypeDefinition)
        .where(ResponseTypeDefinition.session_id == review_session.id)
        .where(ResponseTypeDefinition.response_type == "1-to-5int")
    ).scalar_one()
    rtd_list = db.execute(
        select(ResponseTypeDefinition)
        .where(ResponseTypeDefinition.session_id == review_session.id)
        .where(ResponseTypeDefinition.response_type == "Yes_no")
    ).scalar_one()
    instrument = _instrument(db, review_session.id)

    new_int = instruments_service.add_response_field(
        db,
        instrument=instrument,
        field_key="rating_new",
        label="Rating",
        response_type="1-to-5int",
        required=False,
        help_text=None,
        help_text_visible=True,
        actor=actor,
    )
    new_list = instruments_service.add_response_field(
        db,
        instrument=instrument,
        field_key="verdict",
        label="Verdict",
        response_type="Yes_no",
        required=False,
        help_text=None,
        help_text_visible=True,
        actor=actor,
    )
    db.flush()
    db.refresh(new_int)
    db.refresh(new_list)

    # Numeric row: inline bounds match the RTD verbatim.
    assert new_int._inline_data_type == rtd_int.data_type
    assert new_int._inline_response_type == "1-to-5int"
    assert new_int._inline_min == rtd_int.min
    assert new_int._inline_max == rtd_int.max
    assert new_int._inline_step == rtd_int.step
    assert new_int._inline_list_csv is None
    # List row: list_csv inlined; numeric bounds NULL.
    assert new_list._inline_data_type == rtd_list.data_type
    assert new_list._inline_response_type == "Yes_no"
    assert new_list._inline_min is None
    assert new_list._inline_max is None
    assert new_list._inline_step is None
    assert new_list._inline_list_csv == rtd_list.list_csv


# --------------------------------------------------------------------------- #
# Segment 18J Wave 2 PR ii — .response_type / .data_type properties
# now prefer the inline columns over the RTD-tier relationship.
# --------------------------------------------------------------------------- #


def test_wave2_pr_ii_property_prefers_inline_over_rtd(
    client: TestClient, db: Session
) -> None:
    """The .response_type / .data_type properties on
    InstrumentResponseField now read from the inline columns when
    set, only falling back to response_type_definition when inline
    is NULL. Verify by mutating the inline columns to a value the
    RTD doesn't carry and asserting the property returns the
    inline value."""
    from app.db.models import ResponseTypeDefinition, User
    from app.services import instruments as instruments_service

    review_session = _make_session(client, db, code="w2-prii")
    actor = db.execute(select(User).limit(1)).scalar_one()
    client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    rtd_int = db.execute(
        select(ResponseTypeDefinition)
        .where(ResponseTypeDefinition.session_id == review_session.id)
        .where(ResponseTypeDefinition.response_type == "1-to-5int")
    ).scalar_one()
    instrument = _instrument(db, review_session.id)
    field = instruments_service.add_response_field(
        db,
        instrument=instrument,
        field_key="rating_new",
        label="Rating",
        response_type="1-to-5int",
        required=False,
        help_text=None,
        help_text_visible=True,
        actor=actor,
    )
    db.flush()
    db.refresh(field)

    # Sanity: post-listener, inline columns mirror the RTD; the
    # properties agree with both.
    assert field._inline_response_type == "1-to-5int"
    assert field.response_type == "1-to-5int"
    assert field.data_type == rtd_int.data_type

    # Mutate the inline columns to a sentinel the RTD doesn't
    # carry. The property must return the inline value, not the
    # (still-unchanged) RTD value.
    field._inline_response_type = "Inline_Sentinel"
    field._inline_data_type = "Inline_DT_Sentinel"
    db.flush()
    assert field.response_type == "Inline_Sentinel"
    assert field.data_type == "Inline_DT_Sentinel"
    assert rtd_int.response_type == "1-to-5int"

    # PR iii-b1 retired the RTD-relationship fallback on these
    # properties: clearing inline now returns the empty string
    # (the inline columns are the only source of truth post-iii-b1).
    field._inline_response_type = None
    field._inline_data_type = None
    db.flush()
    assert field.response_type == ""
    assert field.data_type == ""


# --------------------------------------------------------------------------- #
# Segment 18J Wave 2 PR iii-b1 — production creators explicitly populate
# inline columns via inline_kwargs_from_rtd; before_insert listener stays
# as a test-edge-case safety net only.
# --------------------------------------------------------------------------- #


def test_wave2_pr_iii_b1_inline_kwargs_helper_shape(db: Session) -> None:
    """``inline_kwargs_from_rtd`` returns a kwargs dict whose keys
    line up with the InstrumentResponseField inline columns. Each
    creator splatting it via ``**`` populates all six in one go."""
    from app.db.models import ResponseTypeDefinition
    from app.services.instruments._response_fields import (
        inline_kwargs_from_rtd,
    )

    rtd = ResponseTypeDefinition(
        session_id=0,  # unused for this shape test
        response_type="Sentinel_int",
        data_type="Integer",
        min=1.0,
        max=9.0,
        step=1.0,
        list_csv=None,
    )
    kwargs = inline_kwargs_from_rtd(rtd)
    assert set(kwargs.keys()) == {
        "_inline_data_type",
        "_inline_response_type",
        "_inline_min",
        "_inline_max",
        "_inline_step",
        "_inline_list_csv",
    }
    assert kwargs["_inline_data_type"] == "Integer"
    assert kwargs["_inline_response_type"] == "Sentinel_int"
    assert kwargs["_inline_min"] == 1.0
    assert kwargs["_inline_max"] == 9.0
    assert kwargs["_inline_step"] == 1.0
    assert kwargs["_inline_list_csv"] is None


def test_wave2_pr_iii_b1_property_no_longer_falls_back_to_rtd(
    client: TestClient, db: Session
) -> None:
    """The RTD-relationship fallback on the ``.response_type`` /
    ``.data_type`` properties is gone in iii-b1. A row whose
    inline columns are NULL returns "" even though the RTD it
    points at is still present (List-type RTDs survive iii-a)."""
    from app.db.models import ResponseTypeDefinition, User
    from app.services import instruments as instruments_service

    review_session = _make_session(client, db, code="w2-iiib1-nofallback")
    actor = db.execute(select(User).limit(1)).scalar_one()
    client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    )
    rtd_list = db.execute(
        select(ResponseTypeDefinition)
        .where(ResponseTypeDefinition.session_id == review_session.id)
        .where(ResponseTypeDefinition.response_type == "Yes_no")
    ).scalar_one()
    instrument = _instrument(db, review_session.id)
    field = instruments_service.add_response_field(
        db,
        instrument=instrument,
        field_key="yn",
        label="Verdict",
        response_type="Yes_no",
        required=False,
        help_text=None,
        help_text_visible=True,
        actor=actor,
    )
    db.flush()
    db.refresh(field)

    # Sanity: creator populated inline. iii-b4 retired the FK
    # column + the response_type_definition relationship; the
    # phantom response_type_id property returns None.
    assert field._inline_response_type == "Yes_no"
    assert field.response_type_id is None
    assert field.response_type == "Yes_no"

    # Clear inline; reads return the empty string (no fallback
    # anywhere — the relationship is gone too).
    field._inline_response_type = None
    field._inline_data_type = None
    db.flush()
    assert field.response_type == ""
    assert field.data_type == ""
    # ``rtd_list`` is unused now that the FK is gone; reference it
    # to keep ruff quiet.
    assert rtd_list.id is not None


def test_wave3_prii_invalid_field_shape_returns_422(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR ii — authoring-shape validation. A payload whose
    bounds don't make sense (max < min on an integer field) gets
    rejected with 422 and a structured detail listing each offending
    field. The Band 3 ✓ button is client-side-gated against the same
    check; this exercises the defence-in-depth path."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-prii-invalid"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Backwards bounds",
                    "data_type": "integer",
                    "min": "10",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_field_shape"
    assert body["errors"][0]["field_label"] == "Backwards bounds"
    assert "at least" in body["errors"][0]["message"].lower()


def test_step_must_be_at_most_max_minus_min(
    client: TestClient, db: Session
) -> None:
    """Authoring-shape validation — a Step larger than (Max − Min)
    leaves only Min as a valid value, so the Step bound adds no
    expressive power. Server rejects with 422; the Band 3 ✓ button
    is client-side-gated against the same check. Equal-to-range is
    accepted (yields exactly two values: Min and Max — useful for
    Boolean-like numeric fields, e.g. 0/1)."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="step-range"
    )

    # min=1, max=5, step=10 → (5-1) = 4, 10 > 4 → invalid.
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Step too big",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "10",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_field_shape"
    assert "at least two" in body["errors"][0]["message"].lower()

    # Boolean-like — min=0, max=1, step=1 → step == range, accepted
    # (yields exactly two values: 0, 1).
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Boolean-like",
                    "data_type": "integer",
                    "min": "0",
                    "max": "1",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 200

    # min=1, max=5, step=4 → equal to range, accepted (yields 1, 5).
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Step equals range",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "4",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 200

    # min=1.0, max=5.0, step=4.5 → (5-1) = 4, 4.5 > 4 → invalid.
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "name": "Decimal step too big",
                    "data_type": "decimal",
                    "min": "1.0",
                    "max": "5.0",
                    "step": "4.5",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 422


def test_wave3_prii_shape_change_blocked_when_responses_exist(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR ii — once a response field has saved responses, any
    data_type / bounds change is blocked with 409. The Band 3 row's
    data_type select + bound inputs are rendered ``disabled`` when
    ``has_responses`` is true; this server guard catches direct API
    hits. The operator-side workflow is to clear responses first."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-prii-shape-change"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    # Round-trip Rating's id into JSON so the subsequent update path
    # is exercised (rather than the new-row path).
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )

    # Attach a Response to the rating row.
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().first()
    assignment = Assignment(
        session_id=review_session.id,
        instrument_id=new_model.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="4",
        )
    )
    db.commit()

    # Try to change Rating's data_type to string — should be blocked.
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "string",
                    "max": "100",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "shape_change_blocked"
    assert body["field_label"] == "Rating"
    assert body["responses"] == 1
    assert "data_type" in body["changed"]


def test_wave3_prii_label_rename_allowed_when_responses_exist(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR ii — label / name changes don't invalidate existing
    responses (decision 9 locks ``field_key`` stable across renames),
    so the shape-change guard must NOT fire when only the label
    changes. Counterpart to
    test_wave3_prii_shape_change_blocked_when_responses_exist."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-prii-rename-allowed"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().first()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().first()
    assignment = Assignment(
        session_id=review_session.id,
        instrument_id=new_model.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="4",
        )
    )
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Overall Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                }
            ]
        },
    )
    assert response.status_code == 200
    db.refresh(rating)
    assert rating.label == "Overall Rating"


def test_wave3_priii_band2_state_drops_response_fields_key(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR iii — ``set_band2_state`` no longer persists
    ``response_fields`` into the JSON dict. DB rows are the source
    of truth (decision 5). After a Save, ``band2_state`` carries
    only the surviving keys (``selected_display_keys``,
    ``sample_reviewee_name``, ``sample_group_member_ids``)."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-priii-no-rfs"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "selected_display_keys": ["reviewee.name"],
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "required": True,
                }
            ],
        },
    )
    assert resp.status_code == 200
    db.refresh(new_model)
    # JSON dict carries the other keys but NOT response_fields.
    assert new_model.band2_state is not None
    assert "response_fields" not in new_model.band2_state
    assert new_model.band2_state["selected_display_keys"] == ["reviewee.name"]
    # The DB row still reflects the incoming required flag.
    db.refresh(rating)
    assert rating.required is True


def test_wave3_priii_response_field_width_migrates_to_column_widths(
    client: TestClient, db: Session
) -> None:
    """Wave 3 PR iii — ``width_px`` on a response field entry no
    longer lands in ``band2_state.response_fields`` (which is gone)
    but instead routes into ``instrument.column_widths["rf_<id>"]``
    so reviewer-surface ``<col style="width: Npx">`` can pick it up
    and render the same width the operator saw in the Band 2
    preview."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w3-priii-rf-width"
    )
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "width_px": 240,
                }
            ]
        },
    )
    db.refresh(new_model)
    assert new_model.column_widths is not None
    assert new_model.column_widths.get(f"rf_{rating.id}") == 240
    assert "response_fields" not in (new_model.band2_state or {})


def test_wave3_priii_reviewer_surface_emits_response_column_width(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Wave 3 PR iii — once response-column widths land on
    ``column_widths["rf_<id>"]``, the reviewer surface emits the
    matching ``<col style="width: Npx">`` so the table column
    visually matches what the operator saw in the Band 2 preview."""
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="w3-priii-surface-rfw")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Rae",
                email="r@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
                status="active",
            ),
        ]
    )
    db.commit()
    source = _instrument(db, review_session.id)
    operator.post(
        f"/operator/sessions/{review_session.id}/instruments/add-new-model",
        data={"after": str(source.id)},
        follow_redirects=False,
    )
    new_model = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != source.id)
    ).scalar_one()
    rating = next(
        rf for rf in new_model.response_fields if rf.label == "Rating"
    )
    operator.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{new_model.id}/band2-state",
        json={
            "response_fields": [
                {
                    "id": rating.id,
                    "name": "Rating",
                    "data_type": "integer",
                    "min": "1",
                    "max": "5",
                    "step": "1",
                    "selected": True,
                    "width_px": 260,
                }
            ]
        },
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session.id)
    # Pick out the new-model instrument's position from the reviewer
    # page; only that instrument has the operator-set width.
    instruments = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order, Instrument.id)
    ).scalars().all()
    new_model_position = (
        [i.id for i in instruments].index(new_model.id) + 1
    )
    rae_client = make_client(reviewer_user)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/{new_model_position}"
    ).text
    assert "width: 260px" in body


# --------------------------------------------------------------------------- #
# Wave 4 PR 1 — Full Matrix default for new-model NULL rule_set
# --------------------------------------------------------------------------- #


def test_new_model_untouched_band1_generates_full_matrix(
    client: TestClient, db: Session
) -> None:
    """Wave 4 PR 1 — a new-model instrument with untouched Band 1
    (Link 1 + Link 2 both in 'all' mode → no SessionRuleSet
    materialised → ``rule_set_id IS NULL``) is no longer silently
    skipped by ``replace_assignments``. The engine treats it as
    Full Matrix and produces every (reviewer, reviewee) pair."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w4-default-matrix"
    )
    # Add a second reviewer + reviewee so Full Matrix produces > 1 pair
    # — makes the count assertion meaningful.
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Bob",
                email="bob@example.edu",
                tag_1="Lead",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Dan",
                email_or_identifier="dan@example.edu",
                tag_1="Team A",
                tag_2="beta",
                status="active",
            ),
        ]
    )
    db.commit()

    # No Band 1 save, no rule pin. Just hit Generate.
    resp = generate_via_page_button(client, review_session.id)
    assert resp.status_code == 303

    # rule_set_id stayed NULL — we didn't materialise a SessionRuleSet.
    db.refresh(new_model)
    assert new_model.rule_set_id is None

    # Full Matrix: 2 reviewers × 2 reviewees = 4 assignments.
    rows = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.instrument_id == new_model.id,
        )
    ).scalars().all()
    assert len(rows) == 4
    pair_set = {(r.reviewer_id, r.reviewee_id) for r in rows}
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalars().all()
    reviewees = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalars().all()
    expected = {(rv.id, re.id) for rv in reviewers for re in reviewees}
    assert pair_set == expected


def test_new_model_untouched_band1_activates_and_accepts_responses(
    client: TestClient, db: Session
) -> None:
    """Wave 4 PR 1 — activation flips ``accepting_responses=True`` on
    new-model instruments with NULL ``rule_set_id`` (Full Matrix
    default). The legacy ``group_kind + rule_set_id IS NULL`` skip
    no longer triggers for new-model rows."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w4-default-activate"
    )
    # Delete the legacy source instrument so the session has only the
    # new-model row. (``_new_model_with_tags`` seeds a legacy
    # ``source`` instrument as the anchor for ``add-new-model``; it's
    # not relevant to this test and would carry NULL rule_set_id
    # itself.)
    source = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.id != new_model.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/{source.id}/delete",
        follow_redirects=False,
    )
    generate_via_page_button(client, review_session.id)
    _activate(client, db, review_session.id)

    db.refresh(new_model)
    assert new_model.rule_set_id is None  # still NULL
    assert new_model.accepting_responses is True


# --------------------------------------------------------------------------- #
# Progress pills flush-left above the table (reviewer surface + Band 2)
# --------------------------------------------------------------------------- #


def test_band2_intro_progress_pills_render_inside_preview_row(
    client: TestClient, db: Session
) -> None:
    """The progress pills sit inside the Band 2 preview div, wrapped
    in a flex row alongside the per-field min/max/step reminders
    (rs-progress-row). Mirrors the reviewer-surface layout: the
    pills + constraints share a single right-aligned line just
    above the preview table."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-pills-row"
    )
    new_model.short_label = "Sanity"
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())

    intro_idx = flat.find("data-new-model-band2-intro-card")
    assert intro_idx != -1
    # Preview div comes after the intro card's closing tags.
    preview_idx = flat.find("data-new-model-band2-preview", intro_idx)
    assert preview_idx != -1
    # Progress pill lives INSIDE the preview div, wrapped in the
    # rs-progress-row flex container (justify-content: flex-end).
    progress_idx = flat.find("data-new-model-intro-progress", preview_idx)
    assert progress_idx != -1
    between = flat[preview_idx:progress_idx]
    assert "rs-progress-row" in between
    assert "justify-content: flex-end" in between


def test_band2_intro_unified_edit_save_at_card_bottom_right(
    client: TestClient, db: Session
) -> None:
    """The intro card carries a single ✎ / ✓ pair at its bottom-right
    corner that opens / saves BOTH the short_label and description
    edit boxes in one go. Matches the help-text card placement
    (``bottom: 4px; right: 4px``). Per-field ✎ / ✓ pairs no longer
    render."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="band2-intro-unified-edit"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())

    # Per-field onclick handlers retired — only the unified pair
    # is wired. (Substring checks on the attribute names would
    # collide with ``data-intro-short-label-edit-wrap`` which is
    # the kept wrapper span.)
    assert "newModelIntroShortLabelEdit(this)" not in flat
    assert "newModelIntroShortLabelSave(this)" not in flat
    assert "newModelIntroDescriptionEdit(this)" not in flat
    assert "newModelIntroDescriptionSave(this)" not in flat

    # Unified ✎ / ✓ live on the card with bottom-right placement
    # matching the help-text card pattern.
    edit_idx = flat.find("data-intro-edit ")
    save_idx = flat.find("data-intro-save ")
    assert edit_idx != -1 and save_idx != -1
    edit_tag = flat[
        flat.rfind("<button", 0, edit_idx) : flat.find(">", edit_idx) + 1
    ]
    save_tag = flat[
        flat.rfind("<button", 0, save_idx) : flat.find(">", save_idx) + 1
    ]
    for tag in (edit_tag, save_tag):
        assert "position: absolute" in tag
        assert "bottom: 4px" in tag
        assert "right: 4px" in tag
    # Initial state: ✎ visible, ✓ hidden.
    assert "hidden" not in edit_tag
    assert " hidden" in save_tag

    # The unified edit handlers are wired.
    assert "newModelIntroEdit(this)" in edit_tag
    assert "newModelIntroSave(this)" in save_tag





def test_reviewer_surface_progress_pills_render_in_flex_row_above_table(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface's progress pills sit in a single right-
    aligned flex row (``rs-progress-row``) just above the review
    table — sharing the row with any per-field min/max/step
    reminders (the ``rs-constraints muted`` block). The pills are
    outside the ``.rs-instrument-card`` and inline before the
    constraints text."""
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="rs-pills-outside")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Rae",
                email="r@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
                status="active",
            ),
        ]
    )
    db.commit()
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator, review_session.id)
    _activate(operator, db, review_session.id)

    rae_client = make_client(reviewer_user)
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/1"
    ).text
    flat = " ".join(body.split())
    # The flex row appears after the intro card's closing tags and
    # before the table wrapper, and it wraps the pills.
    card_idx = flat.find("rs-instrument-card")
    row_idx = flat.find("rs-progress-row", card_idx)
    progress_idx = flat.find("rs-instrument-progress", row_idx)
    table_idx = flat.find("table-scroll", progress_idx)
    assert card_idx != -1 and row_idx != -1 and progress_idx != -1 and table_idx != -1
    # The card's closing </div></div> sits between the card opening
    # and the flex row.
    between = flat[card_idx:row_idx]
    assert "</div> </div>" in between or "</div></div>" in between
    # The flex row is right-aligned.
    row_tag = flat[row_idx : flat.find(">", row_idx)]
    assert "justify-content: flex-end" in row_tag


# --------------------------------------------------------------------------- #
# Wave 4 — Lock / Unlock toggle replaces per-instrument Edit / Cancel
# --------------------------------------------------------------------------- #


def test_lock_unlock_replaces_edit_button_in_view_mode(
    client: TestClient, db: Session
) -> None:
    """An instrument card in view mode (no ``?editing=`` param) carries
    an ``Unlock`` button at the end of the action row (after
    +New model) — the previous ``Edit`` button retires. Clicking
    Unlock takes the operator to ``?editing=<id>``, the same URL
    state Edit used to reach. The toggle button carries
    ``data-instrument-lock-toggle=<id>`` for test + JS scoping."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w4-lock-toggle-view"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    flat = " ".join(body.split())

    # Edit / Cancel button text retires.
    assert ">Edit</a>" not in flat
    assert ">Cancel</a>" not in flat

    # The Unlock toggle exists on the new-model instrument's row
    # and links to the editing URL.
    toggle_marker = f'data-instrument-lock-toggle="{new_model.id}"'
    toggle_idx = flat.find(toggle_marker)
    assert toggle_idx != -1
    toggle_tag = flat[
        flat.rfind("<a", 0, toggle_idx) : flat.find(">", toggle_idx) + 1
    ]
    assert "Unlock" in flat[flat.find(">", toggle_idx) + 1 : flat.find("</a>", toggle_idx)]
    assert f"editing={new_model.id}" in toggle_tag

    # The toggle sits AFTER the +New model button in the row (the
    # last action before the toggle is +New model).
    new_model_btn_idx = flat.rfind("+New model", 0, toggle_idx)
    assert new_model_btn_idx != -1, "Unlock toggle must come after +New model"


def test_lock_unlock_replaces_cancel_button_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    """An instrument card in edit mode (``?editing=<id>``) carries a
    ``Lock`` button — clicking takes the operator back to view mode
    (``/instruments`` without the editing param). The Save button
    sits beside it (mirrors Quick Setup card's Submit + Lock
    footer). ``Edit`` / ``Cancel`` retire."""
    review_session, new_model = _new_model_with_tags(
        client, db, code="w4-lock-toggle-edit"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={new_model.id}"
    ).text
    flat = " ".join(body.split())

    assert ">Edit</a>" not in flat
    assert ">Cancel</a>" not in flat

    # Lock button on the editing instrument's row.
    toggle_marker = f'data-instrument-lock-toggle="{new_model.id}"'
    toggle_idx = flat.find(toggle_marker)
    assert toggle_idx != -1
    label = flat[flat.find(">", toggle_idx) + 1 : flat.find("</a>", toggle_idx)]
    assert "Lock" in label and "Unlock" not in label
    toggle_tag = flat[
        flat.rfind("<a", 0, toggle_idx) : flat.find(">", toggle_idx) + 1
    ]
    # The Lock href clears the editing param.
    assert "editing=" not in toggle_tag

    # Save button is present (still scoped to ``form=dfsave-<id>``)
    # and sits beside Lock.
    save_form_attr = f'form="dfsave-{new_model.id}"'
    save_idx = flat.find(save_form_attr)
    assert save_idx != -1
    # Save comes before Lock in the row.
    assert save_idx < toggle_idx
