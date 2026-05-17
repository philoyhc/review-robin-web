"""Unit coverage for the canonical-shape validation gate.

PR 8 of Segment 11K. ``audit.write_event`` validates every emitted
``detail`` against ``EVENT_SCHEMAS`` before the row is written:

- Strict mode (``settings.audit_strict_mode=True``, the default in
  tests/conftest.py) raises ``AuditDetailValidationError``.
- Lenient mode (production default) logs a structured warning and
  writes the row anyway — auditing is observability; dropping
  events would hide mutations.
- Every emitted ``event_type`` has a registered schema.

The integration-level "this emit produces this row" coverage lives
in the per-feature tests; this file pins the gate itself.
"""
from __future__ import annotations

import re
import warnings

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession, User
from app.services import audit


def _make_user_and_session(db: Session, code: str) -> tuple[User, ReviewSession]:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return user, review_session


# --------------------------------------------------------------------------- #
# Registry coverage
# --------------------------------------------------------------------------- #


def test_every_emitted_event_type_has_a_registered_schema() -> None:
    """The registry must cover every ``event_type`` the codebase emits.

    Re-derived statically from the migration plan in
    ``guide/segment_11K_audit_event_detail_schema.md``. Adding a
    new emitter without registering its schema fails this test —
    forces deliberate registration so PR 8's validation gate
    knows what shape to expect.
    """
    expected = {
        # PR 1 — session lifecycle
        "session.created",
        "session.updated",
        "session.deleted",
        "session.validated",
        "session.invalidated",
        "session.activated",
        "session.reverted_to_draft",
        "instrument.opened",
        "instrument.closed",
        # PR 2 — instruments
        "response_type.added",
        "response_type.updated",
        "response_type.deleted",
        "instrument.created",
        "instrument.deleted",
        "instrument.display_field_added",
        "instrument.display_field_updated",
        "instrument.display_field_deleted",
        "instrument.display_field_moved",
        "instrument.field_added",
        "instrument.field_updated",
        "instrument.field_deleted",
        "instrument.fields_reordered",
        "instrument.display_fields_saved",
        "instrument.response_fields_saved",
        "instrument.described",
        "instrument.short_label_updated",
        "instruments.bulk_accepting_responses",
        "instruments.bulk_visibility_when_closed",
        # PR 3 — invitations
        "invitations.generated",
        "invitation.regenerated",
        "invitations.regenerated",
        "invitation.sent",
        "invitation.opened",
        "reminders.sent",
        # PR 4 — responses
        "responses.saved",
        "responses.submitted",
        "responses.cleared",
        "responses.deleted_all",
        # PR 5 — assignments
        "assignments.generated",
        "assignments.deleted_all",
        # PR 7 — settings
        "reviewers.imported",
        "reviewees.imported",
        "reviewers.deleted_all",
        "reviewees.deleted_all",
        "operator_email_settings.updated",
        "operator_email_settings.cleared",
        "email_template.updated",
        "email_template.reset",
        # Segment 18A — session tagging
        "session.tag_added",
        "session.tag_removed",
    }
    missing = expected - set(audit.EVENT_SCHEMAS.keys())
    assert not missing, (
        f"event_types missing from EVENT_SCHEMAS: {sorted(missing)}"
    )


# --------------------------------------------------------------------------- #
# Strict-mode (test default)
# --------------------------------------------------------------------------- #


def test_strict_mode_default_in_tests() -> None:
    assert settings.audit_strict_mode is True


def test_strict_mode_rejects_unknown_top_level_key(db: Session) -> None:
    """A pre-canonical idiosyncratic key (e.g. ``instrument_id`` at
    the top level of detail) fails the structural Pydantic check."""
    user, review_session = _make_user_and_session(db, "strict-shape")
    with pytest.raises(audit.AuditDetailValidationError) as exc:
        audit.write_event(
            db,
            event_type="instrument.field_added",
            summary="bad",
            actor_user_id=user.id,
            session_id=review_session.id,
            detail={"instrument_id": 7, "session_id": review_session.id},
        )
    assert exc.value.event_type == "instrument.field_added"


def test_strict_mode_rejects_unregistered_event_type(db: Session) -> None:
    user, review_session = _make_user_and_session(db, "strict-unreg")
    with pytest.raises(audit.AuditDetailValidationError, match="not registered"):
        audit.write_event(
            db,
            event_type="some.brand_new_event_with_no_schema",
            summary="bad",
            actor_user_id=user.id,
            session=review_session,
            payload=audit.counts(things=1),
        )


def test_strict_mode_rejects_disallowed_envelope_for_event(
    db: Session,
) -> None:
    """`session.invalidated` allows reason but not snapshot — a
    snapshot envelope here would be drift back into mixed-concerns."""
    user, review_session = _make_user_and_session(db, "strict-envelope")
    with pytest.raises(audit.AuditDetailValidationError, match="not allowed"):
        audit.write_event(
            db,
            event_type="session.invalidated",
            summary="bad",
            actor_user_id=user.id,
            session=review_session,
            payload=audit.snapshot({"id": review_session.id}),
            reason="setup_mutation",
        )


def test_strict_mode_rejects_set_changes_with_extra_keys(db: Session) -> None:
    """The set_changes envelope is locked to {added, removed, updated}.
    A fourth key indicates someone tried to extend the envelope ad-hoc."""
    user, review_session = _make_user_and_session(db, "strict-setch")
    with pytest.raises(audit.AuditDetailValidationError):
        audit.write_event(
            db,
            event_type="invitations.generated",
            summary="bad",
            actor_user_id=user.id,
            session_id=review_session.id,
            detail={
                "session_id": review_session.id,
                "session_code": review_session.code,
                "set_changes": {
                    "added": [],
                    "removed": [],
                    "updated": [],
                    "weird_key": [],
                },
            },
        )


# --------------------------------------------------------------------------- #
# Canonical-path emits pass under strict mode
# --------------------------------------------------------------------------- #


def test_canonical_emit_passes_strict(db: Session) -> None:
    """Sanity check: a properly-shaped canonical emit doesn't trip
    the strict-mode gate. Covers every envelope at least once."""
    user, review_session = _make_user_and_session(db, "ok-canon")
    audit.write_event(
        db,
        event_type="session.updated",
        summary="ok",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"name": ["A", "B"]}),
    )
    audit.write_event(
        db,
        event_type="instrument.fields_reordered",
        summary="ok",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"order": [["a"], ["b"]]}),
        refs={"instrument_id": 1},
    )
    audit.write_event(
        db,
        event_type="instruments.bulk_accepting_responses",
        summary="ok",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.set_changes(updated=[{"instrument_id": 1}]),
        context={"target": True},
    )
    audit.write_event(
        db,
        event_type="responses.saved",
        summary="ok",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(saved=1, validation_errors=0),
        refs={"reviewer_id": 1},
    )


def test_session_deleted_canonical_no_top_level_identity_passes(
    db: Session,
) -> None:
    """`session.deleted` has detail without top-level identity slots
    because its FK column is null. The schema allows only `snapshot`
    for this event."""
    user, review_session = _make_user_and_session(db, "ok-deleted")
    original_id = review_session.id
    audit.write_event(
        db,
        event_type="session.deleted",
        summary="ok",
        actor_user_id=user.id,
        session=None,
        payload=audit.snapshot({"id": original_id, "code": "ok-deleted", "name": "X"}),
    )


def test_operator_email_settings_cleared_with_none_detail_passes(
    db: Session,
) -> None:
    """The cleared event has no payload at all (legitimately empty)."""
    user, _ = _make_user_and_session(db, "ok-cleared")
    audit.write_event(
        db,
        event_type="operator_email_settings.cleared",
        summary="ok",
        actor_user_id=user.id,
        session=None,
    )


# --------------------------------------------------------------------------- #
# Lenient-mode escape hatch
# --------------------------------------------------------------------------- #


def test_lenient_mode_logs_and_writes_anyway(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production lenient mode lets the row through with a warning so
    a shape bug doesn't hide the mutation it was auditing."""
    monkeypatch.setattr(settings, "audit_strict_mode", False)
    user, review_session = _make_user_and_session(db, "lenient")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        event = audit.write_event(
            db,
            event_type="instrument.field_added",
            summary="bad-but-survives",
            actor_user_id=user.id,
            session_id=review_session.id,
            detail={
                "instrument_id": 7,
                "session_id": review_session.id,
            },
        )
    assert event.id is not None
    assert event.detail == {
        "instrument_id": 7,
        "session_id": review_session.id,
    }
    matched = [
        w for w in caught
        if re.search(r"instrument\.field_added", str(w.message))
    ]
    assert matched, (
        "lenient mode should emit a UserWarning naming the event_type "
        "so the shape violation is visible in production logs"
    )
