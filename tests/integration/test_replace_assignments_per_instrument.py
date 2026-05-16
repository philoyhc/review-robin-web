"""Slice 1 coverage for the per-instrument refactor of
``replace_assignments``.

The function reads each instrument's pinned ``rule_set_id``, runs the
engine internally per-instrument, writes per-instrument
``Assignment`` rows, and emits one ``assignments.generated`` audit
event per processed instrument with ``refs.instrument_id`` set.
Instruments with NULL ``rule_set_id`` are skipped silently.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments
from app.services.instruments import ensure_default_instrument


def _seed_two_instruments(db: Session) -> tuple[
    User,
    ReviewSession,
    Instrument,
    Instrument,
    SessionRuleSet,
]:
    """Two instruments, one ``SessionRuleSet`` (Full Matrix). The
    caller decides which instruments to pin to it.
    """
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code="slice1",
        created_by_user_id=user.id,
        self_reviews_active=True,
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Bob",
                email="bob@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Dan",
                email_or_identifier="dan@example.edu",
            ),
        ]
    )
    db.flush()
    inst_a = ensure_default_instrument(db, review_session)
    inst_b = Instrument(
        session_id=review_session.id,
        name="Peer survey",
        order=2,
    )
    db.add(inst_b)
    db.flush()
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
        is_seeded=True,
    )
    db.add(rule_set)
    db.flush()
    return user, review_session, inst_a, inst_b, rule_set


def test_only_pinned_instruments_get_rows(db: Session) -> None:
    """Cross-instrument default skips instruments with NULL
    ``rule_set_id`` silently."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    # inst_b stays NULL — should be silently skipped.
    db.flush()

    replaced, new = assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )

    rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    instrument_ids = {r.instrument_id for r in rows}
    assert instrument_ids == {inst_a.id}
    # 2 reviewers × 2 reviewees = 4 pairs × 1 pinned instrument.
    assert len(rows) == 4
    assert (replaced, new) == (0, 4)


def test_no_pinned_instruments_is_noop(db: Session) -> None:
    """Zero pinned instruments returns ``(0, 0)`` and writes nothing —
    not an error condition."""

    user, review_session, *_ = _seed_two_instruments(db)
    # No pinning on either instrument.

    replaced, new = assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )

    assert (replaced, new) == (0, 0)
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is None
    )
    # No audit event either — nothing materialised.
    assert (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "assignments.generated",
            )
        ).first()
        is None
    )


def test_one_event_per_pinned_instrument(db: Session) -> None:
    """Each processed instrument fires its own ``assignments.generated``
    event with ``refs.instrument_id``."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    inst_b.rule_set_id = rule_set.id
    db.flush()

    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )

    events = list(
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "assignments.generated",
            )
            .order_by(AuditEvent.id)
        ).scalars()
    )
    assert len(events) == 2
    seen_instrument_ids = {
        e.detail["refs"]["instrument_id"] for e in events
    }
    assert seen_instrument_ids == {inst_a.id, inst_b.id}
    for event in events:
        assert event.detail["counts"]["instruments"] == 1
        # Each event scopes its rule_set_id ref to the session-tier
        # row pinned to that instrument.
        assert event.detail["refs"]["rule_set_id"] == rule_set.id


def test_scoped_replace_only_touches_named_instrument(db: Session) -> None:
    """``instrument_id=<id>`` deletes only that instrument's rows and
    writes only that instrument's fan-out — other instruments'
    Assignment rows survive."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    inst_b.rule_set_id = rule_set.id
    db.flush()

    # First, materialise both instruments.
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )

    # Now scoped re-generate on inst_a only. Should leave inst_b rows
    # untouched.
    replaced, new = assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=inst_a.id,
    )

    # 4 rows replaced on inst_a, 4 new on inst_a, 4 untouched on inst_b.
    assert (replaced, new) == (4, 4)
    inst_a_rows = assignments.existing_count(
        db, review_session.id, instrument_id=inst_a.id
    )
    inst_b_rows = assignments.existing_count(
        db, review_session.id, instrument_id=inst_b.id
    )
    assert inst_a_rows == 4
    assert inst_b_rows == 4


def test_scoped_replace_rejects_unpinned_instrument(db: Session) -> None:
    """``instrument_id=<id>`` against an instrument with NULL
    ``rule_set_id`` raises — the caller named a target that has no
    rule pinned. The cross-instrument default *silently skips* the
    same condition; the named-target path is strict because the
    caller is asserting intent."""

    user, review_session, inst_a, inst_b, _rule_set = _seed_two_instruments(db)
    # inst_b stays unpinned.
    db.flush()

    with pytest.raises(ValueError, match="no rule pinned"):
        assignments.replace_assignments(
            db,
            review_session=review_session,
            user=user,
            correlation_id="c1",
            instrument_id=inst_b.id,
        )


def test_regenerate_clears_responses_on_replaced_assignments(
    db: Session,
) -> None:
    """Regenerating assignments for an instrument that already has
    submitted responses removes the dependent ``responses`` rows
    instead of tripping the FK constraint.

    The per-instrument delete is a bulk Core statement, which bypasses
    the ORM ``delete-orphan`` cascade on ``Assignment.responses``; the
    service must clear the responses explicitly.
    """

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    db.flush()

    # First materialisation — gives inst_a a set of Assignment rows.
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )

    # Attach a response to one of inst_a's assignments.
    rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Rating",
        data_type="number",
    )
    db.add(rtd)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst_a.id,
        field_key="score",
        label="Score",
        response_type_id=rtd.id,
    )
    db.add(field)
    db.flush()
    an_assignment = db.execute(
        select(Assignment).where(Assignment.instrument_id == inst_a.id)
    ).scalars().first()
    db.add(
        Response(
            assignment_id=an_assignment.id,
            response_field_id=field.id,
            value="5",
        )
    )
    db.flush()
    db.commit()

    # Regenerate — must not raise an IntegrityError.
    replaced, new = assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=inst_a.id,
    )

    assert (replaced, new) == (4, 4)
    # The orphaned response was cleared with its assignment.
    assert (
        db.execute(select(Response)).first() is None
    )


def test_existing_count_filters_by_instrument(db: Session) -> None:
    """``existing_count(..., instrument_id=...)`` scopes the count."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    inst_b.rule_set_id = rule_set.id
    db.flush()

    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )

    assert assignments.existing_count(db, review_session.id) == 8
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=inst_a.id
        )
        == 4
    )
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=inst_b.id
        )
        == 4
    )


def test_delete_all_scoped_keeps_other_instruments(db: Session) -> None:
    """``delete_all_assignments(..., instrument_id=...)`` deletes only
    the named instrument's rows and leaves ``assignment_mode``
    untouched (the session is still rule-based on other
    instruments)."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    inst_b.rule_set_id = rule_set.id
    db.flush()

    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )
    mode_before = review_session.assignment_mode
    assert mode_before is not None

    assignments.delete_all_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=inst_a.id,
    )

    db.refresh(review_session)
    # Mode untouched — other instrument still has its rows.
    assert review_session.assignment_mode == mode_before
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=inst_a.id
        )
        == 0
    )
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=inst_b.id
        )
        == 4
    )
