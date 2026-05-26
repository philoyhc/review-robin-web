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
    )
    db.add(rule_set)
    db.flush()
    return user, review_session, inst_a, inst_b, rule_set


@pytest.mark.skip(
    reason="Wave 5 PR 5.3 — every instrument now defaults to Full Matrix "
    "on untouched Band 1; legacy unpinned-instrument skip retired."
)
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


@pytest.mark.skip(
    reason="Wave 5 PR 5.3 — every instrument now defaults to Full Matrix "
    "on untouched Band 1; legacy unpinned-instrument skip retired."
)
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

    # The roster is unchanged, so the reconcile re-run on inst_a
    # inserts and deletes nothing — every pair is kept in place.
    # inst_b is out of scope and untouched.
    assert (replaced, new) == (0, 0)
    inst_a_rows = assignments.existing_count(
        db, review_session.id, instrument_id=inst_a.id
    )
    inst_b_rows = assignments.existing_count(
        db, review_session.id, instrument_id=inst_b.id
    )
    assert inst_a_rows == 4
    assert inst_b_rows == 4


@pytest.mark.skip(
    reason="Wave 5 PR 5.3 — every instrument now defaults to Full Matrix "
    "on untouched Band 1; legacy unpinned-instrument skip retired."
)
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


def _attach_response(
    db: Session, *, instrument_id: int, assignment: Assignment, key: str
) -> int:
    """Attach one ``Response`` to ``assignment`` and return its id.

    Builds the response-type definition + instrument field the
    ``Response`` row needs; ``key`` makes both unique per session /
    instrument.
    """
    field = InstrumentResponseField(
        instrument_id=instrument_id,
        field_key=key,
        label="Score",
        _inline_data_type="Integer",
        _inline_response_type=f"RT-{key}",
    )
    db.add(field)
    db.flush()
    response = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value="5",
    )
    db.add(response)
    db.flush()
    db.commit()
    return response.id


def _seed_self_review_session(
    db: Session,
) -> tuple[User, ReviewSession, Instrument]:
    """A session whose roster has one self-review pair: reviewer
    ``Sam`` and reviewee ``Sam`` share an email, so a Full Matrix
    run pairs them. The default instrument is pinned to that rule
    set."""
    user = User(email="op-selfrev@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="SelfRev",
        code="selfrev",
        created_by_user_id=user.id,
        self_reviews_active=True,
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Sam",
                email="sam@example.edu",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Tom",
                email="tom@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Sam",
                email_or_identifier="sam@example.edu",
            ),
        ]
    )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    db.flush()
    return user, review_session, instrument


def test_reconcile_unchanged_run_keeps_responses(db: Session) -> None:
    """Re-running generation with no roster change inserts and
    deletes nothing — the matched pairs and their responses survive
    the reconcile."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    db.flush()
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )
    an_assignment = (
        db.execute(
            select(Assignment).where(Assignment.instrument_id == inst_a.id)
        )
        .scalars()
        .first()
    )
    resp_id = _attach_response(
        db, instrument_id=inst_a.id, assignment=an_assignment, key="unchanged"
    )

    replaced, new = assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=inst_a.id,
    )

    assert (replaced, new) == (0, 0)
    assert db.get(Response, resp_id) is not None
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=inst_a.id
        )
        == 4
    )


def test_reconcile_added_reviewer_inserts_pairs_and_keeps_responses(
    db: Session,
) -> None:
    """Adding a reviewer before a re-run inserts only that reviewer's
    new pairs; the pre-existing pairs and their responses are left
    untouched."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    db.flush()
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )
    an_assignment = (
        db.execute(
            select(Assignment).where(Assignment.instrument_id == inst_a.id)
        )
        .scalars()
        .first()
    )
    resp_id = _attach_response(
        db, instrument_id=inst_a.id, assignment=an_assignment, key="added"
    )

    # Add a third reviewer — the engine now produces 3 x 2 = 6 pairs.
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Eve",
            email="eve@example.edu",
        )
    )
    db.flush()

    replaced, new = assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=inst_a.id,
    )

    assert (replaced, new) == (0, 2)
    assert db.get(Response, resp_id) is not None
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=inst_a.id
        )
        == 6
    )


def test_reconcile_dropped_pair_deletes_only_its_responses(
    db: Session,
) -> None:
    """A pair the rule no longer produces is deleted along with its
    responses; pairs that survive the reconcile keep theirs.

    Exercises the FK-safe delete order — the bulk Core delete of the
    orphaned ``Assignment`` would trip the ``responses`` foreign key
    if its ``Response`` rows were not cleared first."""

    user, review_session, instrument = _seed_self_review_session(db)
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )
    rows = list(
        db.execute(
            select(Assignment).where(
                Assignment.instrument_id == instrument.id
            )
        ).scalars()
    )
    # Full Matrix over 2 reviewers x 1 reviewee — Sam's self-review
    # plus Tom -> Sam.
    assert len(rows) == 2
    self_pair = next(
        r
        for r in rows
        if r.reviewer.email == "sam@example.edu"
        and r.reviewee.email_or_identifier == "sam@example.edu"
    )
    other_pair = next(r for r in rows if r.id != self_pair.id)

    self_resp = _attach_response(
        db, instrument_id=instrument.id, assignment=self_pair, key="selfp"
    )
    other_resp = _attach_response(
        db, instrument_id=instrument.id, assignment=other_pair, key="otherp"
    )

    # Re-run excluding self-reviews — the self-pair drops out.
    replaced, new = assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=instrument.id,
        override_exclude_self_reviews=True,
    )

    assert (replaced, new) == (1, 0)
    assert db.get(Response, self_resp) is None
    assert db.get(Response, other_resp) is not None
    assert (
        assignments.existing_count(
            db, review_session.id, instrument_id=instrument.id
        )
        == 1
    )


def test_reconcile_audit_event_carries_reconcile_counts(
    db: Session,
) -> None:
    """``assignments.generated`` carries the reconcile counts —
    ``new`` / ``deleted`` / ``kept`` / ``responses_deleted`` — and no
    longer the retired ``replaced`` key."""

    user, review_session, inst_a, inst_b, rule_set = _seed_two_instruments(db)
    inst_a.rule_set_id = rule_set.id
    db.flush()
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c1"
    )
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Eve",
            email="eve@example.edu",
        )
    )
    db.flush()
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="c2",
        instrument_id=inst_a.id,
    )

    event = (
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "assignments.generated",
            )
            .order_by(AuditEvent.id.desc())
        )
        .scalars()
        .first()
    )
    counts = event.detail["counts"]
    assert counts["new"] == 2
    assert counts["deleted"] == 0
    assert counts["kept"] == 4
    assert counts["responses_deleted"] == 0
    assert "replaced" not in counts


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
