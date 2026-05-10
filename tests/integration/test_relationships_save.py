"""Integration coverage for ``save_relationships`` (Segment 15D PR 1).

Pins the wipe-and-replace contract + audit emission + lifecycle
invalidation that 12A-3 PR 2's Manage page upload form will rely
on. No HTTP route yet — that ships in 12A-3 PR 2; this file
exercises the service-layer save directly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import RelationshipImportRow
from app.services import relationships as relationships_service
from app.services import session_lifecycle as lifecycle


def _seed(
    db: Session, *, status: str = "draft"
) -> tuple[User, ReviewSession, Reviewer, Reviewer, Reviewee, Reviewee]:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code=f"rel-save-{status}",
        created_by_user_id=user.id,
        status=status,
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
        email_or_identifier="dan-2026",
    )
    db.add_all([alice, bob, carol, dan])
    db.flush()
    return user, review_session, alice, bob, carol, dan


def _row(reviewer: Reviewer, reviewee: Reviewee, **overrides: object) -> RelationshipImportRow:
    payload: dict[str, object] = {
        "reviewer_id": reviewer.id,
        "reviewee_id": reviewee.id,
    }
    payload.update(overrides)
    return RelationshipImportRow.model_validate(payload)


def test_save_inserts_rows_into_empty_table(db: Session) -> None:
    user, review_session, alice, bob, carol, dan = _seed(db)
    rows = [
        _row(alice, carol, tag_1="Mentor"),
        _row(bob, dan, tag_3="Prior cohort", status="inactive"),
    ]

    replaced, new = relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=rows,
        filename="rel.csv",
        correlation_id="corr-1",
    )

    assert (replaced, new) == (0, 2)
    assert relationships_service.existing_count(db, review_session.id) == 2

    persisted = relationships_service.list_for_session(db, review_session.id)
    by_pair = {(r.reviewer_id, r.reviewee_id): r for r in persisted}
    assert by_pair[(alice.id, carol.id)].tag_1 == "Mentor"
    assert by_pair[(alice.id, carol.id)].status == "active"
    assert by_pair[(bob.id, dan.id)].tag_3 == "Prior cohort"
    assert by_pair[(bob.id, dan.id)].status == "inactive"


def test_save_replaces_existing_rows(db: Session) -> None:
    user, review_session, alice, bob, carol, dan = _seed(db)

    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[_row(alice, carol, tag_1="Mentor")],
        filename="first.csv",
        correlation_id="corr-1",
    )
    assert relationships_service.existing_count(db, review_session.id) == 1

    replaced, new = relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[
            _row(bob, dan, tag_2="COI"),
            _row(alice, dan),
        ],
        filename="second.csv",
        correlation_id="corr-2",
    )

    assert (replaced, new) == (1, 2)
    persisted = relationships_service.list_for_session(db, review_session.id)
    assert {(r.reviewer_id, r.reviewee_id) for r in persisted} == {
        (bob.id, dan.id),
        (alice.id, dan.id),
    }


def test_save_emits_audit_event(db: Session) -> None:
    user, review_session, alice, _bob, carol, _dan = _seed(db)
    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[_row(alice, carol)],
        filename="rel.csv",
        correlation_id="corr-audit",
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "relationships.imported",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = event.detail
    assert detail["counts"]["new"] == 1
    assert detail["counts"]["replaced"] == 0
    assert detail["context"]["filename"] == "rel.csv"
    assert event.correlation_id == "corr-audit"


def test_save_invalidates_validated_session(db: Session) -> None:
    """Mid-cycle relationships edits drop a validated session back
    to draft (mirrors the roster-import lifecycle gate)."""

    user, review_session, alice, _bob, carol, _dan = _seed(
        db, status=lifecycle.SessionStatus.validated.value
    )

    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[_row(alice, carol)],
        filename="rel.csv",
        correlation_id="corr-inv",
    )

    db.refresh(review_session)
    assert review_session.status == lifecycle.SessionStatus.draft.value


def test_save_with_zero_rows_clears_table(db: Session) -> None:
    """An empty Relationships CSV upload wipes the existing rows
    (consistent with the roster wipe-and-replace contract)."""

    user, review_session, alice, _bob, carol, _dan = _seed(db)
    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[_row(alice, carol)],
        filename="seed.csv",
        correlation_id="corr-seed",
    )

    replaced, new = relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[],
        filename="empty.csv",
        correlation_id="corr-empty",
    )

    assert (replaced, new) == (1, 0)
    assert relationships_service.existing_count(db, review_session.id) == 0


def test_pair_context_lookup_returns_keyed_dict(db: Session) -> None:
    """The eager-loaded lookup the engine consumes (15D PR 4)."""

    user, review_session, alice, bob, carol, dan = _seed(db)
    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=[
            _row(alice, carol, tag_1="Mentor"),
            _row(bob, dan, tag_2="COI"),
        ],
        filename="rel.csv",
        correlation_id="corr-lookup",
    )

    lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )
    assert set(lookup.keys()) == {(alice.id, carol.id), (bob.id, dan.id)}
    assert lookup[(alice.id, carol.id)].tag_1 == "Mentor"
    assert lookup[(bob.id, dan.id)].tag_2 == "COI"


def test_save_isolates_per_session(db: Session) -> None:
    user_a, sess_a, alice_a, _b, carol_a, _d = _seed(db)
    relationships_service.save_relationships(
        db,
        session=sess_a,
        user=user_a,
        rows=[_row(alice_a, carol_a)],
        filename="a.csv",
        correlation_id="corr-a",
    )

    user_b = User(email="op-b@example.edu", display_name="Op B")
    db.add(user_b)
    db.flush()
    sess_b = ReviewSession(
        name="Other",
        code="rel-save-other",
        created_by_user_id=user_b.id,
    )
    db.add(sess_b)
    db.flush()
    alice_b = Reviewer(
        session_id=sess_b.id, name="Alice", email="alice@example.edu"
    )
    carol_b = Reviewee(
        session_id=sess_b.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    db.add_all([alice_b, carol_b])
    db.flush()
    relationships_service.save_relationships(
        db,
        session=sess_b,
        user=user_b,
        rows=[_row(alice_b, carol_b, tag_1="Other-session tag")],
        filename="b.csv",
        correlation_id="corr-b",
    )

    rows_b = db.execute(
        select(Relationship).where(Relationship.session_id == sess_b.id)
    ).scalars().all()
    assert {r.tag_1 for r in rows_b} == {"Other-session tag"}
    assert relationships_service.existing_count(db, sess_a.id) == 1
