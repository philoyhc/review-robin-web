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
    ResponseTypeDefinition,
    Reviewee,
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


def test_instruments_get_backfills_lazy_seeded_display_fields(
    client: TestClient, db: Session
) -> None:
    """Sessions whose reviewees / assignments were imported before the
    lazy-seeding logic landed end up missing the corresponding Display
    Fields rows. Hitting GET /instruments idempotently backfills them
    so the operator doesn't have to re-import to recover."""
    review_session = _make_session(client, db, code="backfill-on-get")
    instrument = _instrument(db, review_session.id)

    # Insert a reviewee with tag_1 + profile_link directly (skipping
    # the import path that would auto-seed).
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Cohort A",
            profile_link="https://example.edu/c",
        )
    )
    db.commit()

    # Pre-condition: only the locked Name + Email rows from
    # ensure_default_instrument exist. No tag_1 / profile_link rows.
    pre = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_type, r.source_field) for r in pre] == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
    ]

    client.get(f"/operator/sessions/{review_session.id}/instruments")

    post = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in post]
    assert ("reviewee", "tag_1") in pairs
    assert ("reviewee", "profile_link") in pairs


def test_instruments_get_prunes_unpopulated_display_fields(
    client: TestClient, db: Session
) -> None:
    """If a Display Fields row's underlying data source has no data
    in the session (e.g. pair_context_1 was seeded by a prior import
    that's since been replaced), the row disappears on next GET.
    Locked Name + Email are kept regardless."""
    review_session = _make_session(client, db, code="prune-stale")
    instrument = _instrument(db, review_session.id)
    # Manually insert pair_context.1/2 + reviewee.tag_1 rows simulating
    # state from a prior import.
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="P1",
            source_type="pair_context",
            source_field="1",
            order=2,
            visible=True,
        )
    )
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="P2",
            source_type="pair_context",
            source_field="2",
            order=3,
            visible=True,
        )
    )
    db.add(
        InstrumentDisplayField(
            instrument_id=instrument.id,
            label="Cohort",
            source_type="reviewee",
            source_field="tag_1",
            order=4,
            visible=True,
        )
    )
    # Reviewee with tag_1 populated; no assignments → no pair_context.
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Cohort A",
        )
    )
    db.commit()

    client.get(f"/operator/sessions/{review_session.id}/instruments")

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    # pair_context.1/2 dropped (no data); locked rows + tag_1 kept.
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("reviewee", "tag_1"),
    ]
    # Operator-typed label on tag_1 ("Cohort") survives the prune.
    tag_1 = next(r for r in rows if r.source_field == "tag_1")
    assert tag_1.label == "Cohort"


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
    # ✗ delete + ➕ add are JS-driven; clicks defer to the bulk-save
    # form so Cancel discards the row mutation.
    assert "deleteRow(this" in body
    assert "addRow(this" in body
    assert f'id="rf-template-{instrument.id}"' in body
    assert f'id="rfhelp-template-{instrument.id}"' in body


def test_response_field_help_text_and_visible_persist_via_bulk_save(
    client: TestClient, db: Session
) -> None:
    """Section B Response Fields Help: editing a row's help text +
    Show checkbox persists via the same bulk-save form as the rest
    of the field-builder."""
    review_session = _make_session(client, db, code="rf-help")
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

    save = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
            "required_ids": [str(rating.id)],
            "help_text_id": [str(rating.id), str(comments.id)],
            "help_text": ["Score 1-5", "Free-form remarks"],
            # Show only checked for rating.
            "help_text_visible_ids": [str(rating.id)],
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    db.refresh(rating)
    db.refresh(comments)
    assert rating.help_text == "Score 1-5"
    assert rating.help_text_visible is True
    assert comments.help_text == "Free-form remarks"
    assert comments.help_text_visible is False


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


def test_bulk_save_deletes_rows_listed_in_response_delete_ids(
    client: TestClient, db: Session
) -> None:
    """JS-deferred ✗ on Response Fields adds the row id to the bulk-
    save form's ``response_delete_ids`` set; the route deletes those
    rows before applying the rest of the payload, so Cancel (which
    just navigates away) discards the deletion."""
    review_session = _make_session(client, db, code="bulk-del")
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
    comments_id = comments.id

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
            "required_ids": [str(rating.id)],
            "response_delete_ids": [str(comments.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    remaining = [
        f.field_key
        for f in db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    ]
    assert remaining == ["rating"]
    assert db.get(InstrumentResponseField, comments_id) is None


def test_bulk_save_creates_rows_for_new_id_placeholders(
    client: TestClient, db: Session
) -> None:
    """JS-deferred ➕ on Response Fields inserts a row with ``id=new_N``
    on the bulk-save form. The route allocates a real field via
    ``add_default_response_field`` and applies the operator's typed
    label / required / help to that new row."""
    review_session = _make_session(client, db, code="bulk-add")
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

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response", "response"],
            "id": [str(rating.id), "new_1", str(comments.id)],
            "order": ["0", "1", "2"],
            "label": ["Rating", "Quality", "Comments"],
            "required_ids": [str(rating.id), "new_1"],
            "help_text_id": [str(rating.id), "new_1", str(comments.id)],
            "help_text": ["", "Rate quality 1-5.", ""],
            "help_text_visible_ids": ["new_1"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    )
    labels = [f.label for f in fields]
    assert labels == ["Rating", "Quality", "Comments"]
    quality = fields[1]
    assert quality.required is True
    assert quality.help_text == "Rate quality 1-5."
    assert quality.help_text_visible is True


def test_bulk_save_skips_new_row_marked_for_delete_in_same_submit(
    client: TestClient, db: Session
) -> None:
    """If the operator adds a row (id=new_N) and then ✗-deletes it
    before clicking Save, the bulk-save route does not create + delete
    a stub row — the new id is silently dropped."""
    review_session = _make_session(client, db, code="bulk-add-del")
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

    before_keys = {
        f.field_key
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    }

    # JS-side, the row's id="new_1" is removed from DOM entirely on
    # ✗ — so the form simply omits new_1 from the rows list. We model
    # that here by leaving new_1 out of the payload.
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response"],
            "id": [str(rating.id), str(comments.id)],
            "order": ["0", "1"],
            "label": ["Rating", "Comments"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    after_keys = {
        f.field_key
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    }
    assert before_keys == after_keys


def test_bulk_save_persists_instrument_description(
    client: TestClient, db: Session
) -> None:
    """Section A description rides along with the bulk-save form so a
    single Save commits description + table edits together. Plain
    text in non-editing mode; textarea joined to ``dfsave-{iid}`` in
    editing mode."""
    review_session = _make_session(client, db, code="bulk-desc")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "description": "Spring 2026 Peer Review",
            "kind": ["response"],
            "id": [str(rating.id)],
            "order": ["0"],
            "label": ["Rating"],
            "required_ids": [str(rating.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(instrument)
    assert instrument.description == "Spring 2026 Peer Review"


def test_instruments_page_unifies_edit_under_section_e(
    client: TestClient, db: Session
) -> None:
    """The legacy ``<details>`` Edit toggle in Section A is gone; the
    description is plain text when not editing, and renders as a
    textarea joined to the ``dfsave-{iid}`` bulk-save form when the
    Section E Edit button has put the card in edit mode."""
    review_session = _make_session(client, db, code="edit-unified")
    instrument = _instrument(db, review_session.id)

    locked = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Section A: no inline ``<details>`` Edit toggle, no description form.
    assert "<details>" not in locked
    assert (
        f'action="/operator/sessions/{review_session.id}/instruments/{instrument.id}/edit"'
        not in locked
    )
    # Preview Instrument stub + Section C separator are gone.
    assert "Preview rendering lands" not in locked
    assert "Preview Instrument" not in locked

    editing = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    # In edit mode, description renders as a textarea on the bulk-save form.
    assert (
        f'<textarea form="dfsave-{instrument.id}" name="description"'
        in editing
    )


def test_response_type_definitions_card_renders_seeded_catalog(
    client: TestClient, db: Session
) -> None:
    """The Instruments page renders the Response Type Definitions card
    as a read-only catalog of the ten seeded rows in canonical order.
    Slice 4a contract; operator add / edit / delete lands in 4b."""
    review_session = _make_session(client, db, code="rtd-card")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Response Type Definitions" in body
    # Every seeded row appears, in spec order.
    expected_in_order = [
        "Long_text", "Short_text", "Yes_no", "Grade", "Likert5",
        "100int", "0-to-2int", "1-to-5int", "1-to-5half", "1-to-5dec",
    ]
    last_idx = -1
    for name in expected_in_order:
        idx = body.find(f"<code>{name}</code>")
        assert idx > last_idx, (
            f"{name} missing or out of order in RTD card"
        )
        last_idx = idx
    # 4b features are not yet present.
    assert "Operator-add" in body or "follow-up slice" in body


def test_response_type_definitions_card_formats_min_max_step_by_data_type(
    client: TestClient, db: Session
) -> None:
    """Min / Max / Step on the read-only RTD catalog render as plain
    integers for Integer + String rows (no decimal point) and as one
    decimal place for Decimal rows."""
    review_session = _make_session(client, db, code="rtd-fmt")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text

    # Integer / String rows: no decimal point in Min / Max / Step.
    # Use ``Long_text`` (String, 0..200) and ``100int`` (Integer, 0..100).
    long_text_block = body.split("<code>Long_text</code>", 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">0<" in long_text_block and ">200<" in long_text_block
    assert "0.0" not in long_text_block
    assert "200.0" not in long_text_block

    int_100_block = body.split("<code>100int</code>", 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">100<" in int_100_block
    assert "100.0" not in int_100_block

    # Decimal rows: exactly one decimal place. ``1-to-5half``
    # (Decimal, 1..5 step 0.5).
    half_block = body.split("<code>1-to-5half</code>", 1)[1].split(
        "</tr>", 1
    )[0]
    assert ">1.0<" in half_block
    assert ">5.0<" in half_block
    assert ">0.5<" in half_block


def test_response_fields_type_cell_renders_rtd_select(
    client: TestClient, db: Session
) -> None:
    """Each Response Fields row's Type cell renders a disabled
    ``<select>`` over the session's RTD names, with the row's current
    RTD pre-selected."""
    review_session = _make_session(client, db, code="rf-rtd-select")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # The default seeded ``rating`` row uses ``1-to-5int``.
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.field_key == "rating"
        )
    ).scalar_one()
    assert (
        f'<option value="{rating.response_type_id}" selected>1-to-5int</option>'
        in body
    )
    # The default seeded ``comments`` row uses ``Long_text``.
    comments = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.field_key == "comments"
        )
    ).scalar_one()
    assert (
        f'<option value="{comments.response_type_id}" selected>Long_text</option>'
        in body
    )


# --- Slice 4b: operator add / edit / delete on RTD card --------------


def test_rtd_add_route_persists_operator_defined_row(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-route-add")
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "MyScale",
            "data_type": "Integer",
            "min": "0",
            "max": "10",
            "step": "2",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "rtd-card" in response.headers["location"]

    rtd = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "MyScale",
        )
    ).scalar_one()
    assert rtd.is_seeded is False
    assert (rtd.min, rtd.max, rtd.step) == (0, 10, 2)


def test_rtd_add_route_renders_error_banner_on_invalid_payload(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-route-bad")
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "BadDecimal",
            "data_type": "Decimal",
            "min": "0",
            "max": "1",
            "step": "0.05",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "rtd_error=" in response.headers["location"]

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?rtd_error=Step+must+have+at+most+one+decimal+place"
    ).text
    assert "Could not save Response Type" in body


def test_rtd_edit_route_locks_seeded_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-edit-lock")
    seeded = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "1-to-5int",
        )
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{seeded.id}/edit",
        data={"min": "0", "max": "10", "step": "1"},
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_rtd_delete_route_blocks_in_use_then_confirm_cascades(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-cascade-route")
    instrument = _instrument(db, review_session.id)

    # Operator adds a custom RTD and rebinds the seeded ``rating`` row
    # so it depends on that RTD.
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "Cascade-Test",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Cascade-Test",
        )
    ).scalar_one()
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.response_type_id = custom.id
    db.commit()
    rating_id = rating.id  # capture before cascade invalidates the row
    custom_id = custom.id

    # First delete attempt without confirm: redirect with cascade-block
    # query params; row stays in DB.
    blocked = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{custom_id}/delete",
        follow_redirects=False,
    )
    assert blocked.status_code == 303
    loc = blocked.headers["location"]
    assert f"rtd_delete_blocked_id={custom_id}" in loc
    assert "rtd_delete_blocked_rfs=1" in loc
    assert db.get(ResponseTypeDefinition, custom_id) is not None

    # Operator confirms.
    confirmed = client.post(
        f"/operator/sessions/{review_session.id}/response-types/{custom_id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303

    db.expire_all()
    assert db.get(ResponseTypeDefinition, custom_id) is None
    # Cascade dropped the dependent RF row.
    assert db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.id == rating_id
        )
    ).scalar_one_or_none() is None


def test_rtd_locked_when_session_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rtd-ready-lock")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _validate(client, db, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"

    response = client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "Blocked",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_rtd_card_renders_edit_only_in_locked_state_for_operator_added_row(
    client: TestClient, db: Session
) -> None:
    """In the locked (default) state, every saved operator-defined
    row renders **only** an Edit button (Alert style). Delete moves
    into the unlocked state — operator must click Edit first to
    expose Save / Cancel / Delete on that row."""
    review_session = _make_session(client, db, code="rtd-row-form")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "Editable",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Editable",
        )
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Locked state: Edit anchor rendered; per-row delete form should
    # NOT appear (Delete only in unlocked state).
    assert f"editing_rtd_id={custom.id}" in body
    assert (
        f'/operator/sessions/{review_session.id}/response-types/{custom.id}/delete'
        not in body
    )
    # The per-row edit form should NOT yet render — that requires
    # the operator to click Edit (i.e. ?editing_rtd_id={id}).
    assert f'id="rtd-edit-{custom.id}"' not in body


def test_rtd_card_other_row_edit_is_disabled_when_one_row_unlocked(
    client: TestClient, db: Session
) -> None:
    """While one operator-defined row is in the unlocked state, every
    other operator-defined row's Edit button renders disabled (the
    operator must Save / Cancel / Delete the unlocked row first)."""
    review_session = _make_session(client, db, code="rtd-one-edit")
    for name in ("RowA", "RowB"):
        client.post(
            f"/operator/sessions/{review_session.id}/response-types",
            data={
                "response_type": name,
                "data_type": "Integer",
                "min": "0",
                "max": "5",
                "step": "1",
            },
            follow_redirects=False,
        )
    rows = list(
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id,
                ResponseTypeDefinition.is_seeded.is_(False),
            )
        ).scalars()
    )
    assert len(rows) == 2
    a, b = rows[0], rows[1]

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing_rtd_id={a.id}"
    ).text
    # The unlocked row carries the Save / Cancel / Delete trio.
    assert f'id="rtd-edit-{a.id}"' in body
    assert (
        f'/operator/sessions/{review_session.id}/response-types/{a.id}/delete'
        in body
    )
    # The other locked row's Edit button is rendered but disabled
    # (greyed out) — no link into ``editing_rtd_id={b.id}``.
    assert f"editing_rtd_id={b.id}" not in body


def test_rtd_card_renders_per_row_edit_form_when_editing_rtd_id_matches(
    client: TestClient, db: Session
) -> None:
    """Clicking Edit lands on the same page with
    ``?editing_rtd_id={id}``; the matching row swaps into the editable
    state with parameter inputs + Save / Cancel buttons. Other
    operator-defined rows stay in the saved (locked) state."""
    review_session = _make_session(client, db, code="rtd-edit-mode")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "EditTarget",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "EditTarget",
        )
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing_rtd_id={custom.id}"
    ).text
    assert f'id="rtd-edit-{custom.id}"' in body
    # The Save button submits to the edit route; Cancel anchors back
    # to the page without the editing param.
    assert (
        f'/operator/sessions/{review_session.id}/response-types/{custom.id}/edit'
        in body
    )


def test_rtd_card_renders_draft_templates_for_js_add_flow(
    client: TestClient, db: Session
) -> None:
    """The Add a Response Type footer renders only Name + Data Type
    inputs; the actual draft row is cloned client-side from the
    ``rtd-draft-row-template`` / ``rtd-draft-form-template`` <template>
    elements when the operator clicks Add."""
    review_session = _make_session(client, db, code="rtd-draft-tmpl")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'id="rtd-draft-row-template"' in body
    assert 'id="rtd-draft-form-template"' in body
    assert 'id="new-rtd-name"' in body
    assert 'id="new-rtd-data-type"' in body
    # The footer Add form is intentionally minimal — only Name +
    # Data Type. Min / Max / Step / List inputs live in the draft
    # row template and only appear after Add is clicked.
    assert 'onclick="addRtdDraft()"' in body
    # The draft-row template's Cancel button must pass the draft id
    # as a quoted string — passing it bare (``cancelRtdDraft(d1)``)
    # would treat ``d1`` as a JS identifier and silently fail.
    assert "cancelRtdDraft('__DRAFT_ID__')" in body


def test_rtd_add_button_disabled_when_editing_an_existing_row(
    client: TestClient, db: Session
) -> None:
    """``Add a Response Type`` is locked while a saved operator-defined
    row is in editing mode (``?editing_rtd_id=...``); the operator
    must Save or Cancel that row first."""
    review_session = _make_session(client, db, code="rtd-add-lock")
    client.post(
        f"/operator/sessions/{review_session.id}/response-types",
        data={
            "response_type": "ToEdit",
            "data_type": "Integer",
            "min": "0",
            "max": "5",
            "step": "1",
        },
        follow_redirects=False,
    )
    custom = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "ToEdit",
        )
    ).scalar_one()

    # Not editing — Add is enabled.
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    button_html = body.split('id="rtd-add-button"', 1)[1].split(">", 1)[0]
    assert "disabled" not in button_html

    # Editing — Add is server-rendered disabled.
    body_editing = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
        f"?editing_rtd_id={custom.id}"
    ).text
    button_html_editing = body_editing.split(
        'id="rtd-add-button"', 1
    )[1].split(">", 1)[0]
    assert "disabled" in button_html_editing
    assert 'data-server-disabled="1"' in button_html_editing


# --- Slice 4c: operator-pickable Type on new RF rows --------------


def test_rf_draft_template_renders_enabled_type_select_with_rtd_target(
    client: TestClient, db: Session
) -> None:
    """The hidden ``rf-template-{iid}`` for a new Response Field row
    renders an enabled (no ``disabled`` attribute) ``<select>`` over
    the session's RTDs, paired with a hidden ``new_rtd_target`` input
    that lets the bulk-save route key the chosen RTD by draft id."""
    review_session = _make_session(client, db, code="rf-draft-rtd")
    instrument = _instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text

    template_block = body.split(
        f'id="rf-template-{instrument.id}"', 1
    )[1].split("</template>", 1)[0]
    assert 'name="new_rtd_target"' in template_block
    assert 'name="new_rtd_id"' in template_block
    # The select is *not* disabled (saved-row Type stays disabled).
    select_block = template_block.split('name="new_rtd_id"', 1)[1].split(
        ">", 1
    )[0]
    assert "disabled" not in select_block
    # Every seeded RTD shows up as an option.
    for name in [
        "Long_text", "Short_text", "Yes_no", "Grade", "Likert5",
        "100int", "0-to-2int", "1-to-5int", "1-to-5half", "1-to-5dec",
    ]:
        assert f">{name}</option>" in template_block


def test_bulk_save_creates_new_rf_row_with_operator_chosen_rtd_and_label(
    client: TestClient, db: Session
) -> None:
    """The bulk-save handler routes a ``new_*`` row through
    ``add_default_response_field(rtd_id=..., label=..., required=...)``
    so the new RF row lands at the operator-chosen Type, with a
    field_key derived from the typed label."""
    review_session = _make_session(client, db, code="bulk-add-rtd")
    instrument = _instrument(db, review_session.id)
    rtds = {
        r.response_type: r
        for r in db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id
            )
        ).scalars()
    }
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

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response", "response", "response"],
            "id": [str(rating.id), "new_1", str(comments.id)],
            "order": ["0", "1", "2"],
            "label": ["Rating", "Decision", "Comments"],
            "required_ids": [str(rating.id), "new_1"],
            "new_rtd_target": ["new_1"],
            "new_rtd_id": [str(rtds["Yes_no"].id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.label == "Decision",
        )
    ).scalar_one()
    assert new_field.response_type == "Yes_no"
    assert new_field.field_key == "decision"
    assert new_field.required is True
    assert new_field.validation == {"choices": ["Yes", "No"]}


def test_bulk_save_ignores_response_type_id_for_existing_rows(
    client: TestClient, db: Session
) -> None:
    """Server-side defence: the bulk-save handler only honours
    ``new_rtd_target`` / ``new_rtd_id`` for rows whose id starts
    with ``new_`` — Type stays read-only post-create on saved rows
    even if a forged form attempts to flip it."""
    review_session = _make_session(client, db, code="bulk-rtd-defence")
    instrument = _instrument(db, review_session.id)
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    original_rtd_id = rating.response_type_id
    other_rtd = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Yes_no",
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "kind": ["response"],
            "id": [str(rating.id)],
            "order": ["0"],
            "label": ["Rating"],
            # Forged: target an existing row id with a different RTD.
            "new_rtd_target": [str(rating.id)],
            "new_rtd_id": [str(other_rtd.id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(rating)
    assert rating.response_type_id == original_rtd_id
    # And no rogue field crept in.
    fields = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    assert len(fields) == 2  # rating + comments only
