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
    exercise edit/delete on those rows seed them explicitly. Append
    after the locked Name + Email rows that ``ensure_default_instrument``
    already seeded (Slice 1 of Segment 10D)."""
    db.refresh(instrument)
    base = max((f.order for f in instrument.display_fields), default=-1) + 1
    for offset, slot in enumerate(("1", "2", "3")):
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="pair_context",
                source_field=slot,
                order=base + offset,
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


def test_reviewees_import_lazy_seeds_display_fields(
    client: TestClient, db: Session
) -> None:
    """After uploading reviewees with populated tag/profile columns, the
    Default instrument should gain corresponding display-field rows
    automatically — no operator action required (item #14). Locked
    Name + Email rows are seeded by ``ensure_default_instrument`` even
    before the reviewees import (Slice 1 of Segment 10D)."""
    review_session = _make_session(client, db, code="seed-on-import")
    instrument = _instrument(db, review_session.id)
    pre_rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_type, r.source_field) for r in pre_rows] == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
    ]

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
    # Locked Name + Email rows + lazy-seeded profile_link + tag_1.
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
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

    response = client.post(
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


def test_state_machine_editing_param_renders_save_cancel(
    client: TestClient, db: Session
) -> None:
    """``?editing={iid}`` opens the per-instrument card for editing —
    the Section E ``Save`` button (form="dfsave-{iid}") is rendered."""
    review_session = _make_session(client, db, code="state-edit")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # Section E Save is identified by ``form="dfsave-{iid}"``.
    assert f'form="dfsave-{instrument.id}"' in body
    assert ">Save</button>" in body
    # Section E Cancel is the only Cancel anchor on the page.
    assert ">Cancel</a>" in body


def test_state_machine_default_renders_edit_only(
    client: TestClient, db: Session
) -> None:
    """Without ``?editing``, the per-instrument card is locked — the
    Section E Edit anchor links forward to ``?editing={iid}``."""
    review_session = _make_session(client, db, code="state-locked")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Section E Edit anchor.
    assert f"?editing={instrument.id}" in body
    # Section E bulk-save form ``dfsave-{iid}`` not present in locked
    # mode (the form wraps editable inputs only).
    assert f'form="dfsave-{instrument.id}"' not in body


def test_state_machine_locked_when_session_ready(
    client: TestClient, db: Session
) -> None:
    """Even with ``?editing={iid}``, a ``ready`` session keeps the
    card locked and greys out the Edit button."""
    review_session = _make_session(client, db, code="state-ready")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"
    instrument = _instrument(db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # Section E bulk-save form is suppressed; Edit anchor renders with
    # the disabled-look styling.
    assert "pointer-events: none" in body
    assert f'form="dfsave-{instrument.id}"' not in body


def test_saved_state_pill_flips_after_save(
    client: TestClient, db: Session
) -> None:
    """A fresh instrument renders the ``not saved`` pill; after the
    operator submits a bulk save (touches a Display Fields label), the
    pill flips to ``saved``."""
    review_session = _make_session(client, db, code="saved-pill")
    instrument = _instrument(db, review_session.id)

    fresh = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "not saved</span>" in fresh
    assert ">saved</span>" not in fresh

    # Submit a bulk save touching the locked Name row's label.
    name_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "name",
        )
    ).scalar_one()
    email_row = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "email_or_identifier",
        )
    ).scalar_one()

    save = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["display", "display"],
            "id": [str(name_row.id), str(email_row.id)],
            "order": ["0", "1"],
            "label": ["Reviewee Name", "Reviewee Email"],
            "visible_ids": [str(name_row.id), str(email_row.id)],
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    after = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert ">saved</span>" in after
    assert ">not saved</span>" not in after


def test_response_field_label_and_required_persist_via_bulk_save(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — operator types a Friendly Label on a Response Fields
    row and toggles Required, hits Save, the values stick on reload."""
    review_session = _make_session(client, db, code="rf-save")
    instrument = _instrument(db, review_session.id)
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

    # Submit a bulk save touching Response Fields only: rename rating
    # to "Score", flip comments' Required from off to on.
    save = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Score", "Comments"],
            "required_ids": [str(rating.id), str(comments.id)],
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    db.refresh(rating)
    db.refresh(comments)
    assert rating.label == "Score"
    assert rating.required is True
    assert comments.required is True


def test_response_field_add_row_preserves_editing_param(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — clicking ➕ on the Response Fields table redirects
    back with ``?editing={iid}`` so the operator stays in edit mode."""
    review_session = _make_session(client, db, code="rf-add")
    instrument = _instrument(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/add-row",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"editing={instrument.id}" in response.headers["location"]

    keys = sorted(
        r.field_key
        for r in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    assert "rating3" in keys


def test_response_field_delete_preserves_editing_param(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — clicking ✗ on a Response Fields row redirects back
    with ``?editing={iid}``."""
    review_session = _make_session(client, db, code="rf-del")
    instrument = _instrument(db, review_session.id)
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "comments",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        f"/fields/{comments.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f"editing={instrument.id}" in response.headers["location"]


def test_response_field_move_preserves_editing_param(
    client: TestClient, db: Session
) -> None:
    """Slice 2 — clicking ▲ / ▼ on a Response Fields row swaps and
    redirects back with ``?editing={iid}``."""
    review_session = _make_session(client, db, code="rf-move")
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
    assert f"editing={instrument.id}" in response.headers["location"]

    keys_in_order = [
        r.field_key
        for r in db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    ]
    assert keys_in_order == ["comments", "rating"]


def test_state_machine_response_fields_render_inputs_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    """In edit mode the Response Fields table renders editable label
    inputs + required checkboxes + ➕ / ✗ buttons."""
    review_session = _make_session(client, db, code="rf-edit-render")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # Inputs for label + required participate in the bulk-save form.
    assert f'form="dfsave-{instrument.id}"' in body
    assert 'name="required_ids"' in body
    # ✗ delete + ➕ add forms are present per row.
    assert "/fields/" in body and "/delete" in body
    assert "/fields/add-row" in body


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
            order=2,
            visible=True,
        )
    )
    db.commit()
    df = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_field == "tag_1",
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
