"""Integration coverage for Segment 15D PR 5 — backfill from
``Assignment.context.pair_context_*`` into ``relationships``.

PR 5 ships the backfill in two forms:
- An Alembic data migration that runs once at deploy time.
- A service function (``relationships.backfill_from_assignment_context``)
  giving admin tooling a re-runnable handle and a testable surface.

These tests exercise the service function directly. The Alembic
migration mirrors the same logic in raw SQL; its round-trip on
SQLite + Postgres is verified by the existing migration-roundtrip
gate in ``tests/conftest.py``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import relationships as relationships_service


def _seed_session(
    db: Session, *, code: str
) -> tuple[
    User, ReviewSession, list[Reviewer], list[Reviewee], list[Instrument]
]:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    alice = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    bob = Reviewer(
        session_id=review_session.id, name="Bob", email="bob@example.edu"
    )
    carol = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    dan = Reviewee(
        session_id=review_session.id,
        name="Dan",
        email_or_identifier="dan@example.edu",
    )
    inst1 = Instrument(
        session_id=review_session.id, name="Q1", short_label="Q1", order=0
    )
    inst2 = Instrument(
        session_id=review_session.id, name="Q2", short_label="Q2", order=1
    )
    db.add_all([alice, bob, carol, dan, inst1, inst2])
    db.flush()
    return user, review_session, [alice, bob], [carol, dan], [inst1, inst2]


def _add_assignment(
    db: Session,
    *,
    session_id: int,
    reviewer: Reviewer,
    reviewee: Reviewee,
    instrument: Instrument,
    context: dict[str, str | None] | None = None,
    created_by_mode: str = "manual",
) -> Assignment:
    a = Assignment(
        session_id=session_id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        context=context,
        created_by_mode=created_by_mode,
    )
    db.add(a)
    db.flush()
    return a


def test_backfill_lifts_pair_context_into_relationships(db: Session) -> None:
    user, sess, (alice, bob), (carol, dan), (i1, i2) = _seed_session(
        db, code="bf-mixed"
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context={"pair_context_1": "Mentor", "pair_context_2": "Cohort A"},
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i2,
        context={"pair_context_1": "Mentor", "pair_context_2": "Cohort A"},
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=bob,
        reviewee=dan,
        instrument=i1,
        context={"pair_context_3": "Prior cohort"},
    )

    counts = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-bf",
    )

    assert counts == {"scanned": 2, "migrated": 2, "skipped": 0}

    rows = db.execute(
        select(Relationship)
        .where(Relationship.session_id == sess.id)
        .order_by(Relationship.reviewer_id, Relationship.reviewee_id)
    ).scalars().all()
    assert len(rows) == 2

    by_pair = {(r.reviewer_id, r.reviewee_id): r for r in rows}
    alice_carol = by_pair[(alice.id, carol.id)]
    assert alice_carol.tag_1 == "Mentor"
    assert alice_carol.tag_2 == "Cohort A"
    assert alice_carol.tag_3 is None
    assert alice_carol.status == "active"

    bob_dan = by_pair[(bob.id, dan.id)]
    assert bob_dan.tag_1 is None
    assert bob_dan.tag_2 is None
    assert bob_dan.tag_3 == "Prior cohort"


def test_backfill_skips_assignments_with_empty_context(db: Session) -> None:
    user, sess, (alice, _bob), (carol, _dan), (i1, _i2) = _seed_session(
        db, code="bf-empty"
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context=None,
    )

    counts = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-bf-empty",
    )

    assert counts == {"scanned": 0, "migrated": 0, "skipped": 0}
    assert (
        relationships_service.existing_count(db, sess.id) == 0
    )


def test_backfill_treats_blank_strings_as_missing(db: Session) -> None:
    """Pair_context cells that contain only whitespace shouldn't
    create a relationships row."""

    user, sess, (alice, _bob), (carol, _dan), (i1, _i2) = _seed_session(
        db, code="bf-blank"
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context={"pair_context_1": "   ", "pair_context_2": ""},
    )

    counts = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-bf-blank",
    )
    assert counts == {"scanned": 0, "migrated": 0, "skipped": 0}


def test_backfill_dedupes_by_pair_across_instruments(db: Session) -> None:
    """Two instrument-fanout rows for the same pair carrying
    different non-null tag values per slot — the backfill keeps the
    first non-null per slot."""

    user, sess, (alice, _bob), (carol, _dan), (i1, i2) = _seed_session(
        db, code="bf-dedupe"
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context={"pair_context_1": "Mentor", "pair_context_2": None},
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i2,
        # The same pair on a different instrument added a tag2 value.
        context={"pair_context_1": "Mentor", "pair_context_2": "Cohort A"},
    )

    counts = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-bf-dedupe",
    )
    assert counts["scanned"] == 1
    assert counts["migrated"] == 1
    rows = relationships_service.list_for_session(db, sess.id)
    assert len(rows) == 1
    assert rows[0].tag_1 == "Mentor"
    assert rows[0].tag_2 == "Cohort A"


def test_backfill_idempotent_when_relationship_already_exists(
    db: Session,
) -> None:
    """Re-running the backfill on a session that already has a
    matching relationships row skips the pair (counts.skipped += 1,
    no duplicate insert)."""

    user, sess, (alice, _bob), (carol, _dan), (i1, _i2) = _seed_session(
        db, code="bf-idem"
    )
    db.add(
        Relationship(
            session_id=sess.id,
            reviewer_id=alice.id,
            reviewee_id=carol.id,
            tag_1="Pre-existing",
            status="active",
        )
    )
    db.flush()
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context={"pair_context_1": "Mentor"},
    )

    counts = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-bf-idem",
    )
    assert counts == {"scanned": 1, "migrated": 0, "skipped": 1}
    rows = relationships_service.list_for_session(db, sess.id)
    assert len(rows) == 1
    # The pre-existing row's tag_1 is preserved (skip beats overwrite).
    assert rows[0].tag_1 == "Pre-existing"


def test_backfill_running_twice_is_a_noop(db: Session) -> None:
    user, sess, (alice, _bob), (carol, _dan), (i1, _i2) = _seed_session(
        db, code="bf-twice"
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context={"pair_context_1": "Mentor"},
    )

    first = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-twice-1",
    )
    second = relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-twice-2",
    )
    assert first == {"scanned": 1, "migrated": 1, "skipped": 0}
    assert second == {"scanned": 1, "migrated": 0, "skipped": 1}
    assert relationships_service.existing_count(db, sess.id) == 1


def test_backfill_emits_audit_event(db: Session) -> None:
    user, sess, (alice, _bob), (carol, _dan), (i1, _i2) = _seed_session(
        db, code="bf-audit"
    )
    _add_assignment(
        db,
        session_id=sess.id,
        reviewer=alice,
        reviewee=carol,
        instrument=i1,
        context={"pair_context_1": "Mentor"},
    )

    relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess,
        actor_user_id=user.id,
        correlation_id="corr-audit",
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type
            == "relationships.migrated_from_assignment_context",
            AuditEvent.session_id == sess.id,
        )
    ).scalar_one()
    detail = event.detail
    assert detail["counts"] == {
        "scanned": 1,
        "migrated": 1,
        "skipped": 0,
    }
    assert event.correlation_id == "corr-audit"
    assert event.actor_user_id == user.id


def test_backfill_isolates_per_session(db: Session) -> None:
    """A session's backfill does not touch another session's
    assignments / relationships."""

    user_a, sess_a, (alice_a, _b), (carol_a, _d), (i1_a, _) = _seed_session(
        db, code="bf-iso-a"
    )
    user_b, sess_b, (alice_b, _b), (carol_b, _d), (i1_b, _) = _seed_session(
        db, code="bf-iso-b"
    )
    _add_assignment(
        db,
        session_id=sess_a.id,
        reviewer=alice_a,
        reviewee=carol_a,
        instrument=i1_a,
        context={"pair_context_1": "Tag A"},
    )
    _add_assignment(
        db,
        session_id=sess_b.id,
        reviewer=alice_b,
        reviewee=carol_b,
        instrument=i1_b,
        context={"pair_context_1": "Tag B"},
    )

    relationships_service.backfill_from_assignment_context(
        db,
        review_session=sess_a,
        actor_user_id=user_a.id,
        correlation_id="corr-iso-a",
    )

    rows_a = relationships_service.list_for_session(db, sess_a.id)
    rows_b = relationships_service.list_for_session(db, sess_b.id)
    assert len(rows_a) == 1
    assert rows_a[0].tag_1 == "Tag A"
    assert rows_b == []
