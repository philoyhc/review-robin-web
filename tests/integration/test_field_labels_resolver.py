"""Resolver chain coverage for Segment 15A Slice 1.

Pins the three-step chain in ``app.services.field_labels``:

1. Session-wide override (``session_field_labels`` row)
2. Built-in default in ``_DEFAULT_LABELS`` (12 slots)
3. ``f"{source_type}:{source_field}"`` last-resort fallback

Also covers the 12-slot allowlist (``upsert`` / ``clear`` strict
on unknown slots, ``resolve`` permissive) and the regression
that ``InstrumentDisplayField.label`` no longer feeds the chain.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    ResponseTypeDefinition,
    ReviewSession,
    SessionFieldLabel,
    User,
)
from app.services import audit, field_labels


def _make_session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    return review_session, op


# ── Resolver chain (read path) ────────────────────────────────────────────


def test_resolve_returns_built_in_default_when_no_override(
    db: Session,
) -> None:
    review_session, _ = _make_session(db, "fl-default")
    # No session_field_labels rows; chain falls through to
    # _DEFAULT_LABELS.
    assert (
        field_labels.resolve(review_session, "reviewer", "tag_1") == "Tag 1"
    )
    assert (
        field_labels.resolve(review_session, "reviewee", "name") == "Name"
    )
    assert (
        field_labels.resolve(review_session, "reviewee", "email_or_identifier")
        == "Email"
    )
    assert (
        field_labels.resolve(review_session, "reviewee", "profile_link")
        == "Profile"
    )
    assert (
        field_labels.resolve(review_session, "pair_context", "1")
        == "Pair context 1"
    )


def test_resolve_returns_session_override_when_present(
    db: Session,
) -> None:
    review_session, op = _make_session(db, "fl-override")
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_1",
        label="Lab section",
        user=op,
    )
    # Override wins over the built-in "Tag 1".
    assert (
        field_labels.resolve(review_session, "reviewee", "tag_1")
        == "Lab section"
    )
    # Other slots still fall through.
    assert (
        field_labels.resolve(review_session, "reviewee", "tag_2") == "Tag 2"
    )


def test_resolve_falls_back_to_canonical_string_for_unknown_slot(
    db: Session,
) -> None:
    """Resolver is permissive on read — unknown slots get a usable
    ``{source_type}:{source_field}`` fallback string. Strict
    validation happens in ``upsert`` / ``clear``."""
    review_session, _ = _make_session(db, "fl-unknown")
    assert (
        field_labels.resolve(review_session, "mystery", "orb")
        == "mystery:orb"
    )


def test_resolve_covers_all_12_slots(db: Session) -> None:
    """The full 12-slot allowlist returns a non-fallback default
    label. No slot leaks through to the ``source_type:source_field``
    last-resort string."""
    review_session, _ = _make_session(db, "fl-12slots")
    expected = {
        ("reviewer", "tag_1"): "Tag 1",
        ("reviewer", "tag_2"): "Tag 2",
        ("reviewer", "tag_3"): "Tag 3",
        ("reviewee", "name"): "Name",
        ("reviewee", "email_or_identifier"): "Email",
        ("reviewee", "tag_1"): "Tag 1",
        ("reviewee", "tag_2"): "Tag 2",
        ("reviewee", "tag_3"): "Tag 3",
        ("reviewee", "profile_link"): "Profile",
        ("pair_context", "1"): "Pair context 1",
        ("pair_context", "2"): "Pair context 2",
        ("pair_context", "3"): "Pair context 3",
    }
    for (source_type, source_field), built_in in expected.items():
        assert (
            field_labels.resolve(review_session, source_type, source_field)
            == built_in
        ), f"{source_type}.{source_field} fell through default chain"


def test_all_labels_returns_only_overridden_slots(db: Session) -> None:
    review_session, op = _make_session(db, "fl-all")
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_1",
        label="Cohort",
        user=op,
    )
    field_labels.upsert(
        db,
        review_session,
        source_type="pair_context",
        source_field="2",
        label="Module",
        user=op,
    )
    assert field_labels.all_labels(review_session) == {
        ("reviewee", "tag_1"): "Cohort",
        ("pair_context", "2"): "Module",
    }


def test_resolve_does_not_consult_instrument_display_field_label(
    db: Session,
) -> None:
    """Regression pin for Segment 15A Slice 1: the per-instrument
    ``InstrumentDisplayField.label`` is no longer in the resolver
    chain, even when non-empty."""
    review_session, _ = _make_session(db, "fl-no-pi")
    # Minimal instrument + display field with a per-instrument
    # label that would have won under the pre-15A chain.
    rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Test",
        data_type="String",
    )
    db.add(rtd)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id,
        name="Test Instrument",
        order=0,
    )
    db.add(instrument)
    db.flush()
    field = InstrumentDisplayField(
        instrument_id=instrument.id,
        source_type="reviewee",
        source_field="tag_1",
        label="Per-instrument override (should be ignored)",
        visible=True,
        order=2,
    )
    db.add(field)
    db.flush()
    # Resolver returns the built-in default, not the per-instrument
    # override.
    assert (
        field_labels.resolve(review_session, "reviewee", "tag_1") == "Tag 1"
    )


# ── upsert + clear (write path) ───────────────────────────────────────────


def test_upsert_creates_then_updates_row(db: Session) -> None:
    review_session, op = _make_session(db, "fl-upsert")
    row1 = field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Cohort",
        user=op,
    )
    assert row1.id is not None
    assert row1.label == "Cohort"

    row2 = field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Team",
        user=op,
    )
    assert row2.id == row1.id  # same row, updated in place
    assert row2.label == "Team"

    # Only one row exists for this slot.
    rows = (
        db.execute(
            select(SessionFieldLabel).where(
                SessionFieldLabel.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


def test_upsert_strips_whitespace(db: Session) -> None:
    review_session, op = _make_session(db, "fl-strip")
    row = field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_1",
        label="  Lab section  ",
        user=op,
    )
    assert row.label == "Lab section"


def test_upsert_rejects_empty_label(db: Session) -> None:
    review_session, op = _make_session(db, "fl-empty")
    with pytest.raises(ValueError):
        field_labels.upsert(
            db,
            review_session,
            source_type="reviewer",
            source_field="tag_1",
            label="",
            user=op,
        )
    with pytest.raises(ValueError):
        field_labels.upsert(
            db,
            review_session,
            source_type="reviewer",
            source_field="tag_1",
            label="   ",
            user=op,
        )


def test_upsert_rejects_unknown_source(db: Session) -> None:
    review_session, op = _make_session(db, "fl-bad-src")
    with pytest.raises(field_labels.FieldLabelSourceError):
        field_labels.upsert(
            db,
            review_session,
            source_type="reviewer",
            source_field="name",  # reviewer.name not in allowlist
            label="X",
            user=op,
        )
    with pytest.raises(field_labels.FieldLabelSourceError):
        field_labels.upsert(
            db,
            review_session,
            source_type="mystery",
            source_field="orb",
            label="X",
            user=op,
        )


def test_clear_removes_row(db: Session) -> None:
    review_session, op = _make_session(db, "fl-clear")
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        label="Cohort",
        user=op,
    )
    field_labels.clear(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        user=op,
    )
    # Row is gone, resolver falls back to built-in default.
    rows = (
        db.execute(
            select(SessionFieldLabel).where(
                SessionFieldLabel.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )
    assert rows == []
    assert (
        field_labels.resolve(review_session, "reviewer", "tag_1") == "Tag 1"
    )


def test_clear_is_idempotent(db: Session) -> None:
    """Clearing a slot with no override is a no-op — no error, no
    audit event."""
    review_session, op = _make_session(db, "fl-idem")
    pre_count = db.execute(
        select(audit.AuditEvent).where(
            audit.AuditEvent.event_type == "session_field_label.cleared"
        )
    ).all()
    field_labels.clear(
        db,
        review_session,
        source_type="reviewer",
        source_field="tag_1",
        user=op,
    )
    post_count = db.execute(
        select(audit.AuditEvent).where(
            audit.AuditEvent.event_type == "session_field_label.cleared"
        )
    ).all()
    assert len(pre_count) == len(post_count)


# ── Audit emission ────────────────────────────────────────────────────────


def test_upsert_emits_audit_set_event(db: Session) -> None:
    review_session, op = _make_session(db, "fl-audit-set")
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_1",
        label="Lab section",
        user=op,
    )
    events = (
        db.execute(
            select(audit.AuditEvent).where(
                audit.AuditEvent.event_type == "session_field_label.set",
                audit.AuditEvent.session_id == review_session.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    event = events[0]
    assert event.detail["changes"] == {"label": [None, "Lab section"]}
    assert event.detail["context"] == {
        "source_type": "reviewee",
        "source_field": "tag_1",
    }


def test_upsert_audit_changes_carry_old_value_on_update(
    db: Session,
) -> None:
    review_session, op = _make_session(db, "fl-audit-update")
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_1",
        label="First",
        user=op,
    )
    field_labels.upsert(
        db,
        review_session,
        source_type="reviewee",
        source_field="tag_1",
        label="Second",
        user=op,
    )
    events = (
        db.execute(
            select(audit.AuditEvent)
            .where(
                audit.AuditEvent.event_type == "session_field_label.set",
                audit.AuditEvent.session_id == review_session.id,
            )
            .order_by(audit.AuditEvent.id)
        )
        .scalars()
        .all()
    )
    assert len(events) == 2
    assert events[0].detail["changes"] == {"label": [None, "First"]}
    assert events[1].detail["changes"] == {"label": ["First", "Second"]}


def test_clear_emits_audit_cleared_event(db: Session) -> None:
    review_session, op = _make_session(db, "fl-audit-clr")
    field_labels.upsert(
        db,
        review_session,
        source_type="pair_context",
        source_field="2",
        label="Module",
        user=op,
    )
    field_labels.clear(
        db,
        review_session,
        source_type="pair_context",
        source_field="2",
        user=op,
    )
    events = (
        db.execute(
            select(audit.AuditEvent).where(
                audit.AuditEvent.event_type == "session_field_label.cleared",
                audit.AuditEvent.session_id == review_session.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    event = events[0]
    assert event.detail["snapshot"] == {
        "source_type": "pair_context",
        "source_field": "2",
        "label": "Module",
    }
