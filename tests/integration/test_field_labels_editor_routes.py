"""Per-page friendly-label editor route tests — 15A Slice 3.

Pins the three POST handlers on Reviewers / Reviewees /
Relationships:

- Upsert / clear semantics per slot in one form submit.
- Lifecycle gate — ``is_ready`` returns 409.
- Validation invalidation propagates from
  ``field_labels.upsert`` / ``.clear``.
- Audit emission per modified slot.
- Editor block renders inputs + Save button when not ready,
  disabled + no Save when ready.

The resolver / mutator semantics themselves are covered by
``tests/integration/test_field_labels_resolver.py`` — this file
covers only the route + template wiring.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionFieldLabel, User
from app.services import field_labels


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()
    return review_session


def _actor(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


def _rows(db: Session, session_id: int) -> list[SessionFieldLabel]:
    return list(
        db.execute(
            select(SessionFieldLabel)
            .where(SessionFieldLabel.session_id == session_id)
            .order_by(SessionFieldLabel.source_type, SessionFieldLabel.source_field)
        ).scalars()
    )


# ── Reviewers route ──────────────────────────────────────────────────────


def test_reviewers_save_upserts_three_slots(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rev")
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/field-labels",
        data={"tag_1": "Cohort", "tag_2": "Track", "tag_3": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/reviewers"
    )
    rows = _rows(db, review_session.id)
    assert [(r.source_type, r.source_field, r.label) for r in rows] == [
        ("reviewer", "tag_1", "Cohort"),
        ("reviewer", "tag_2", "Track"),
    ]


def test_reviewers_save_clears_empty_slots(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rev-clear")
    actor = _actor(db)
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Old",
        user=actor,
    )
    # Empty value clears the row.
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/field-labels",
        data={"tag_1": "", "tag_2": "", "tag_3": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert _rows(db, review_session.id) == []


def test_reviewers_save_emits_audit_set_per_slot(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rev-audit")
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/field-labels",
        data={"tag_1": "Cohort", "tag_2": "Track", "tag_3": ""},
        follow_redirects=False,
    )
    set_events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "session_field_label.set",
                AuditEvent.session_id == review_session.id,
            )
        ).scalars()
    )
    # One set event per filled slot. ``tag_3`` empty → ``clear``
    # path, idempotent no-op (no audit).
    assert len(set_events) == 2


def test_reviewers_save_rejects_when_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rev-ready")
    # Forge the session into the ready state to trip the lifecycle
    # gate; the helper short-circuit avoids the full activate dance.
    review_session.status = "ready"
    db.flush()
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/field-labels",
        data={"tag_1": "Cohort"},
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_reviewers_page_renders_editor_when_not_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rev-render")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert "Reviewer tag labels" in body
    assert (
        f'action="/operator/sessions/{review_session.id}/reviewers/field-labels"'
        in body
    )
    assert "Save labels" in body
    assert 'name="tag_1"' in body
    assert 'name="tag_2"' in body
    assert 'name="tag_3"' in body
    # Save + Cancel both render Secondary style, both start
    # ``disabled``, both carry the marker attribute so the inline
    # JS can find them.
    assert "Cancel" in body
    assert 'class="btn secondary"' in body
    assert "data-field-labels-cancel" in body
    assert "data-field-labels-save" in body
    assert 'disabled>Cancel' in body
    assert 'disabled>Save labels' in body


def test_reviewers_page_renders_editor_disabled_when_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rev-readonly")
    review_session.status = "ready"
    db.flush()
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert "Reviewer tag labels" in body
    # Inputs render with ``disabled``; the Save + Cancel buttons
    # are suppressed entirely.
    assert 'name="tag_1"' in body
    assert "disabled" in body
    assert "Save labels" not in body
    assert "data-field-labels-cancel" not in body


# ── Reviewees route (three tag slots) ───────────────────────────────────
#
# Identity columns (Name / Email_Identifier / Profile) retired
# 2026-05-31 per guide/participant_model_upgrade.md §3.7. Only the
# three tag slots remain; identity-slot form fields are silently
# ignored if submitted.


def test_reviewees_save_upserts_three_tag_slots(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-revee")
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/field-labels",
        data={
            "tag_1": "Lab section",
            "tag_2": "",
            "tag_3": "Year",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = _rows(db, review_session.id)
    pairs = {(r.source_field, r.label) for r in rows}
    assert pairs == {
        ("tag_1", "Lab section"),
        ("tag_3", "Year"),
    }


def test_reviewees_save_silently_ignores_retired_identity_slots(
    client: TestClient, db: Session
) -> None:
    """Form fields for the retired identity slots (Name / Email /
    Profile) are silently ignored — the route iterates the allowlist
    and never reads the form field for an unknown slot."""
    review_session = _make_session(client, db, "fle-revee-retired")
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/field-labels",
        data={
            "name": "Student name",
            "email_or_identifier": "Student ID",
            "profile_link": "Photo",
            "tag_1": "Lab section",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = _rows(db, review_session.id)
    # Only the tag slot persisted; identity slots silently dropped.
    pairs = {(r.source_field, r.label) for r in rows}
    assert pairs == {("tag_1", "Lab section")}


def test_reviewees_page_renders_one_row_three_inputs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-revee-render")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert "Reviewee tag labels" in body
    # Three inputs total — the three tag slots.
    for name in ("tag_1", "tag_2", "tag_3"):
        assert f'name="{name}"' in body
    # Retired identity slots no longer present as form inputs.
    for name in ("name", "email_or_identifier", "profile_link"):
        assert f'name="{name}"' not in body


# ── Relationships route (pair_context, "1" / "2" / "3") ──────────────────


def test_relationships_save_upserts_pair_context_slots(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rel")
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/field-labels",
        data={
            "slot_1": "Module",
            "slot_2": "",
            "slot_3": "Section",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = _rows(db, review_session.id)
    assert [(r.source_field, r.label) for r in rows] == [
        ("1", "Module"),
        ("3", "Section"),
    ]


def test_relationships_page_renders_pair_context_editor(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-rel-render")
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert "Pair-context labels" in body
    assert 'name="slot_1"' in body
    assert 'name="slot_2"' in body
    assert 'name="slot_3"' in body
    # Placeholder reads from the resolver's canonical default.
    assert 'placeholder="Pair context 1"' in body


# ── Validation invalidation hook ────────────────────────────────────────


def test_save_invalidates_validated_session(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "fle-invalidate")
    # Forge the session into ``validated``; the upsert flow calls
    # ``lifecycle.invalidate_if_validated`` so the status flips back
    # to draft.
    review_session.status = "validated"
    db.flush()
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/field-labels",
        data={"tag_1": "Cohort"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(review_session)
    assert review_session.status == "draft"
