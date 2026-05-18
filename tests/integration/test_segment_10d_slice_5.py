"""Segment 10D Slice 5 — multi-instrument enable.

Wires the previously-disabled `Add new instrument` and
`Delete this instrument` buttons on the per-instrument card. The
underlying `create_instrument` / `delete_instrument` services and
their POST routes already shipped in 10C; this slice flips the
buttons live with appropriate gates.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _create_session(
    client: TestClient, db: Session, code: str = "slice5"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Slice 5", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_rosters(client: TestClient, db: Session, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
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
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def _validated_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    session = _create_session(client, db, code=code)
    _populate_rosters(client, db, session.id)
    response = client.get(f"/operator/sessions/{session.id}/assignments?validated=1")
    assert response.status_code == 200
    db.refresh(session)
    assert session.status == "validated"
    return session


def _ready_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    session = _validated_session(client, db, code=code)
    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(session)
    assert session.status == "ready"
    return session


def _instruments(db: Session, session_id: int) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )


# --------------------------------------------------------------------------- #
# POST /instruments/add
# --------------------------------------------------------------------------- #


def test_add_instrument_appends_with_seeded_fields_and_audit(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="add-basic")
    [default] = _instruments(db, session.id)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    assert response.status_code == 303

    instruments = _instruments(db, session.id)
    assert len(instruments) == 2
    new = instruments[1]
    assert new.id != default.id
    assert new.order == 1
    # Anchor fragment points at the new card.
    assert response.headers["location"].endswith(f"#instrument-{new.id}")

    response_fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == new.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    )
    assert [rf.field_key for rf in response_fields] == ["rating", "comments"]
    assert response_fields[0].response_type == "1-to-5int"
    assert response_fields[1].response_type == "Long_text"

    display_fields = list(
        db.execute(
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id == new.id)
            .order_by(InstrumentDisplayField.order)
        ).scalars()
    )
    # Two locked rows seeded by source: name + email_or_identifier.
    sources = {(df.source_type, df.source_field) for df in display_fields}
    assert ("reviewee", "name") in sources
    assert ("reviewee", "email_or_identifier") in sources

    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.created")
        .where(AuditEvent.session_id == session.id)
    ).scalar_one()
    assert event.detail["refs"]["instrument_id"] == new.id


def test_add_instrument_with_after_inserts_mid_stack(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="add-after")
    [default] = _instruments(db, session.id)

    # Add two more so we have three instruments at orders 0, 1, 2.
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    second = _instruments(db, session.id)[-1]
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(second.id)},
        follow_redirects=False,
    )

    instruments = _instruments(db, session.id)
    assert len(instruments) == 3
    assert [inst.order for inst in instruments] == [0, 1, 2]

    # Insert a new one immediately after the first; previous orders 1 and
    # 2 should each be bumped by one.
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    assert response.status_code == 303

    instruments = _instruments(db, session.id)
    assert len(instruments) == 4
    assert [inst.order for inst in instruments] == [0, 1, 2, 3]
    # The default (anchor) keeps order 0; the freshly-inserted one is at 1.
    assert instruments[0].id == default.id
    assert instruments[1].id != default.id
    assert instruments[1].id != second.id


def test_add_instrument_clones_existing_full_matrix_assignments(
    client: TestClient, db: Session
) -> None:
    """Adding a new instrument to a session that's already had
    assignments seeded (full-matrix or otherwise) replicates each
    `(reviewer, reviewee, include, context)` pair onto the new
    instrument so it joins the matrix immediately. Without this,
    the reviewer surface hides the new instrument's Page button
    (no assignments → nothing to render)."""
    session = _create_session(client, db, code="add-clone")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
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
        f"/operator/sessions/{session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nC,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session.id)
    generate_via_page_button(client, session.id)
    pre_assignments = (
        db.execute(
            select(Assignment).where(Assignment.session_id == session.id)
        )
        .scalars()
        .all()
    )
    assert len(pre_assignments) == 1  # one (reviewer, reviewee) pair × default

    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    new_instrument = (
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session.id)
            .where(Instrument.id != default.id)
        )
        .scalars()
        .one()
    )
    new_assignments = (
        db.execute(
            select(Assignment)
            .where(Assignment.session_id == session.id)
            .where(Assignment.instrument_id == new_instrument.id)
        )
        .scalars()
        .all()
    )
    assert len(new_assignments) == len(pre_assignments)
    assert new_assignments[0].reviewer_id == pre_assignments[0].reviewer_id
    assert new_assignments[0].reviewee_id == pre_assignments[0].reviewee_id
    assert new_assignments[0].include == pre_assignments[0].include
    assert new_assignments[0].created_by_mode == pre_assignments[0].created_by_mode
    # Audit event records the clone count for traceability.
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.created")
        .where(AuditEvent.session_id == session.id)
    ).scalar_one()
    assert event.detail["context"]["cloned_assignments"] == len(pre_assignments)


def test_add_instrument_with_no_existing_assignments_clones_zero(
    client: TestClient, db: Session
) -> None:
    """Adding an instrument to a session that has no assignments
    yet (e.g. before reviewers / reviewees are imported) succeeds and
    clones zero rows. Audit detail reflects the count."""
    session = _create_session(client, db, code="add-clone-empty")
    [default] = _instruments(db, session.id)

    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    assignments = (
        db.execute(
            select(Assignment).where(Assignment.session_id == session.id)
        )
        .scalars()
        .all()
    )
    assert assignments == []
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.created")
        .where(AuditEvent.session_id == session.id)
    ).scalar_one()
    assert event.detail["context"]["cloned_assignments"] == 0


def test_add_instrument_invalidates_validated_session(
    client: TestClient, db: Session
) -> None:
    session = _validated_session(client, db, code="add-inv")
    [default] = _instruments(db, session.id)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(session)
    assert session.status == "draft"

    inv_event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "session.invalidated")
        .where(AuditEvent.session_id == session.id)
    ).scalar_one()
    assert inv_event.detail.get("reason") == "instrument_added"


def test_add_instrument_returns_409_when_session_ready(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="add-ready")
    [default] = _instruments(db, session.id)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    assert response.status_code == 409

    assert len(_instruments(db, session.id)) == 1


# --------------------------------------------------------------------------- #
# POST /instruments/add-group (Segment 13C placeholder)
# --------------------------------------------------------------------------- #


def test_add_group_instrument_sets_group_kind_and_renders_stub(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="add-group")
    [default] = _instruments(db, session.id)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/add-group",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    assert response.status_code == 303

    instruments = _instruments(db, session.id)
    assert len(instruments) == 2
    new = instruments[1]
    assert new.group_kind == "both"
    assert response.headers["location"].endswith(f"#instrument-{new.id}")

    # The group-scoped card renders as a stub: identity + status +
    # Danger Zone, with a "Group-scoped" chip, and no Display /
    # Response Fields tables.
    page = client.get(f"/operator/sessions/{session.id}/instruments")
    assert page.status_code == 200
    body = page.text
    assert "Group-scoped" in body
    assert "This Instrument's Status" in body
    assert (
        f'action="/operator/sessions/{session.id}/instruments/add-group"'
        in body
    )
    assert ">Replicate</button>" in body


def test_add_group_instrument_returns_409_when_session_ready(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="add-group-ready")

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/add-group",
        follow_redirects=False,
    )
    assert response.status_code == 409
    assert len(_instruments(db, session.id)) == 1


def test_group_instrument_display_fields_editable_and_save(
    client: TestClient, db: Session
) -> None:
    """The group-scoped card's Display Fields Include checkboxes are
    editable and persist via the bulk-save route (Segment 13C PR 1).
    Group instruments have no locked rows, so the Name row can be
    hidden."""
    session = _create_session(client, db, code="grp-edit")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/instruments/add-group",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    group = next(i for i in _instruments(db, session.id) if i.group_kind)

    # Edit mode renders the bulk-save form.
    page = client.get(
        f"/operator/sessions/{session.id}/instruments?editing={group.id}"
    )
    assert page.status_code == 200
    assert f'id="dfsave-{group.id}"' in page.text
    assert 'name="visible_ids"' in page.text

    name_df = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == group.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()
    assert name_df.visible is True

    # Save with the Name row submitted but omitted from visible_ids.
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{group.id}/fields/save",
        data={
            "kind": "display",
            "id": str(name_df.id),
            "order": "0",
            "label": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(name_df)
    assert name_df.visible is False


def test_group_instrument_display_fields_sort_save(
    client: TestClient, db: Session
) -> None:
    """The group-scoped card's Display Fields Sort control persists to
    instruments.sort_display_fields (Segment 13C PR 1)."""
    session = _create_session(client, db, code="grp-sort")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/instruments/add-group",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    group = next(i for i in _instruments(db, session.id) if i.group_kind)

    page = client.get(
        f"/operator/sessions/{session.id}/instruments?editing={group.id}"
    )
    assert page.status_code == 200
    assert 'class="sort-btn"' in page.text
    assert f'id="sort-spec-inputs-{group.id}"' in page.text

    name_df = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == group.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{group.id}/fields/save",
        data={
            "kind": "display",
            "id": str(name_df.id),
            "order": "0",
            "label": "",
            "visible_ids": str(name_df.id),
            "sort_display_field_id": str(name_df.id),
            "sort_dir": "asc",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(group)
    assert group.sort_display_fields == [
        {"display_field_id": name_df.id, "dir": "asc"}
    ]


def test_group_instrument_response_fields_editable_and_save(
    client: TestClient, db: Session
) -> None:
    """The group-scoped card's Response Fields table is editable and a
    label change persists via the bulk-save route (Segment 13C PR 1)."""
    session = _create_session(client, db, code="grp-rf")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/instruments/add-group",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    group = next(i for i in _instruments(db, session.id) if i.group_kind)

    page = client.get(
        f"/operator/sessions/{session.id}/instruments?editing={group.id}"
    )
    assert page.status_code == 200
    assert f'data-rf-tbody="{group.id}"' in page.text
    assert f'id="rf-template-{group.id}"' in page.text

    rf = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == group.id)
        .order_by(InstrumentResponseField.order)
    ).scalars().first()

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{group.id}/fields/save",
        data={
            "kind": "response",
            "id": str(rf.id),
            "order": "0",
            "label": "Renamed Rating",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(rf)
    assert rf.label == "Renamed Rating"


def test_group_instrument_group_by_encodes_group_kind(
    client: TestClient, db: Session
) -> None:
    """Ticking *Group by* on a group-scoped instrument's Display
    Fields tag row encodes the boundary spec into ``group_kind``;
    unticking it reverts to the no-boundary sentinel. The tag row's
    Include (``visible``) is derived from the Group-by tick (Segment
    13C PR 2 slice A)."""
    session = _create_session(client, db, code="grp-by")
    [default] = _instruments(db, session.id)
    # A reviewee tag column seeds a RevieweeTag1 display field on
    # every instrument in the session (re-seeded on the index GET).
    client.post(
        f"/operator/sessions/{session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Team A\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/instruments/add-group",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    group = next(i for i in _instruments(db, session.id) if i.group_kind)
    assert group.group_kind == "both"  # no boundary tag yet

    page = client.get(
        f"/operator/sessions/{session.id}/instruments?editing={group.id}"
    )
    assert page.status_code == 200
    assert 'name="group_by_ids"' in page.text

    tag_df = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == group.id,
            InstrumentDisplayField.source_type == "reviewee",
            InstrumentDisplayField.source_field == "tag_1",
        )
    ).scalar_one()

    # Save with the tag row ticked Group by.
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{group.id}/fields/save",
        data={
            "kind": "display",
            "id": str(tag_df.id),
            "order": "0",
            "label": "",
            "group_by_ids": str(tag_df.id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(group)
    db.refresh(tag_df)
    assert group.group_kind == "r1"
    assert tag_df.visible is True  # Include derived from Group by

    # Save again with Group by unticked → back to the sentinel, and
    # the tag row's derived Include drops to False.
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{group.id}/fields/save",
        data={
            "kind": "display",
            "id": str(tag_df.id),
            "order": "0",
            "label": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(group)
    db.refresh(tag_df)
    assert group.group_kind == "both"
    assert tag_df.visible is False


# --------------------------------------------------------------------------- #
# POST /instruments/{iid}/delete
# --------------------------------------------------------------------------- #


def test_delete_instrument_cascades_and_repacks_order(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="del-basic")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    instruments = _instruments(db, session.id)
    assert len(instruments) == 3
    middle = instruments[1]

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{middle.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    survivors = _instruments(db, session.id)
    assert len(survivors) == 2
    assert middle.id not in {inst.id for inst in survivors}
    # Order repacked to 0..N-1.
    assert [inst.order for inst in survivors] == [0, 1]

    # Cascade: the deleted instrument's RFs and DFs are gone.
    rf_count = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == middle.id
        )
    ).all()
    assert rf_count == []
    df_count = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == middle.id
        )
    ).all()
    assert df_count == []

    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.deleted")
        .where(AuditEvent.session_id == session.id)
    ).scalar_one()
    assert event.detail["refs"]["instrument_id"] == middle.id


def test_delete_instrument_refuses_last_instrument(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="del-last")
    [default] = _instruments(db, session.id)

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{default.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 400

    assert len(_instruments(db, session.id)) == 1


def test_delete_instrument_invalidates_validated_session(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="del-inv")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    # Walk back to validated after the add (which dropped us to draft).
    _populate_rosters(client, db, session.id)
    response = client.get(f"/operator/sessions/{session.id}/assignments?validated=1")
    assert response.status_code == 200
    db.refresh(session)
    assert session.status == "validated"

    second = _instruments(db, session.id)[1]
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{second.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(session)
    assert session.status == "draft"

    inv_events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "session.invalidated")
            .where(AuditEvent.session_id == session.id)
            .order_by(AuditEvent.id)
        ).scalars()
    )
    # The most recent invalidation reason is `instrument_deleted`.
    assert inv_events[-1].detail.get("reason") == "instrument_deleted"


def test_delete_instrument_404_across_session_boundary(
    client: TestClient, db: Session
) -> None:
    session_a = _create_session(client, db, code="del-cross-a")
    session_b = _create_session(client, db, code="del-cross-b")

    [default_a] = _instruments(db, session_a.id)
    # Make session B have multiple instruments so the last-instrument
    # guard isn't what trips us.
    client.post(
        f"/operator/sessions/{session_b.id}/instruments/add",
        data={"after": str(_instruments(db, session_b.id)[0].id)},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{session_b.id}/instruments/{default_a.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 404

    # Session A is untouched.
    assert len(_instruments(db, session_a.id)) == 1


def test_delete_instrument_returns_409_when_session_ready(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="del-ready")
    [default] = _instruments(db, session.id)
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )
    # Re-validate + activate after the add.
    _populate_rosters(client, db, session.id)
    client.get(f"/operator/sessions/{session.id}/assignments?validated=1")
    response = client.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(session)
    assert session.status == "ready"

    second = _instruments(db, session.id)[1]
    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{second.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 409

    assert len(_instruments(db, session.id)) == 2


# --------------------------------------------------------------------------- #
# Template render
# --------------------------------------------------------------------------- #


def test_action_row_renders_add_and_delete_enabled_in_normal_state(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="render-ok")
    [default] = _instruments(db, session.id)
    # Add a second so Delete is enabled (the only-instrument gate
    # otherwise disables it).
    client.post(
        f"/operator/sessions/{session.id}/instruments/add",
        data={"after": str(default.id)},
        follow_redirects=False,
    )

    response = client.get(f"/operator/sessions/{session.id}/instruments")
    assert response.status_code == 200
    body = response.text

    # Legacy placeholder copy is gone.
    assert "Multi-instrument support is still in progress" not in body
    assert "Wiring lands in Slice 5" not in body

    # Form actions are wired.
    assert (
        f'action="/operator/sessions/{session.id}/instruments/add"' in body
    )
    assert (
        f"/operator/sessions/{session.id}/instruments/{default.id}/delete"
        in body
    )

    # Consent checkbox is wired on Delete (replaced the legacy
    # native confirm() onsubmit pattern with the operator-page
    # consent-checkbox vocabulary used elsewhere — see Reviewers /
    # Reviewees / Assignments delete-all forms).
    assert 'name="confirm" value="true" required' in body


def test_delete_button_disabled_when_only_instrument(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="render-only")
    response = client.get(f"/operator/sessions/{session.id}/instruments")
    assert response.status_code == 200
    body = response.text

    # The Danger Zone card is still present, but the Delete button
    # carries the only-instrument tooltip and is disabled.
    assert "Cannot delete the only instrument on this session." in body
    # Add button is enabled in this state — make sure we're checking the
    # right one. The disabled Delete should sit inside a button tag with
    # both `disabled` and the only-instrument title.
    assert (
        'disabled title="Cannot delete the only instrument on this session."'
        in body
    )


def test_action_row_disabled_when_session_ready(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="render-ready")
    response = client.get(f"/operator/sessions/{session.id}/instruments")
    assert response.status_code == 200
    body = response.text

    # The "ready" tooltip wording fires for both Add and Delete.
    assert "Revert to draft to add or delete instruments." in body
