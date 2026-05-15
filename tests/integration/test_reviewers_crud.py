"""Integration coverage for the per-row reviewer CRUD service —
Segment 15F PR 1.

Pins the create / update / bulk-status surface +
``invalidate_if_validated`` invariant + canonical audit envelopes
on every emitter. No HTTP route yet — that ships in PR 3; this
file exercises the service directly.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Reviewer, ReviewSession, User
from app.services import reviewers as reviewers_service
from app.services.reviewers import ReviewerOperationError


def _seed(
    db: Session, *, status: str = "draft"
) -> tuple[User, ReviewSession]:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code=f"reviewers-crud-{status}",
        created_by_user_id=user.id,
        status=status,
    )
    db.add(review_session)
    db.flush()
    return user, review_session


# --------------------------------------------------------------------------- #
# create_reviewer
# --------------------------------------------------------------------------- #


def test_create_reviewer_inserts_row_and_emits_snapshot(db: Session) -> None:
    user, review_session = _seed(db)

    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        tag_1="Mentor",
        user=user,
    )

    assert reviewer.id is not None
    assert reviewer.name == "Alice"
    assert reviewer.email == "alice@example.edu"
    assert reviewer.status == "active"
    assert reviewer.tag_1 == "Mentor"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewer.created")
    ).scalar_one()
    assert event.detail["snapshot"]["reviewer_id"] == reviewer.id
    assert event.detail["snapshot"]["email"] == "alice@example.edu"
    assert event.detail["snapshot"]["status"] == "active"
    assert event.detail["snapshot"]["tag_1"] == "Mentor"
    assert event.detail["snapshot"]["tag_2"] is None


def test_create_reviewer_strips_whitespace_and_normalises_status(
    db: Session,
) -> None:
    user, review_session = _seed(db)

    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="  Alice  ",
        email="alice@example.edu",
        tag_1="  ",  # whitespace-only collapses to None
        status="ACTIVE",
        user=user,
    )

    assert reviewer.name == "Alice"
    assert reviewer.tag_1 is None
    assert reviewer.status == "active"


def test_create_reviewer_rejects_empty_name(db: Session) -> None:
    user, review_session = _seed(db)

    with pytest.raises(ReviewerOperationError) as exc_info:
        reviewers_service.create_reviewer(
            db,
            review_session=review_session,
            name="   ",
            email="alice@example.edu",
            user=user,
        )
    assert exc_info.value.code == "empty_name"


def test_create_reviewer_rejects_invalid_email(db: Session) -> None:
    user, review_session = _seed(db)

    with pytest.raises(ReviewerOperationError) as exc_info:
        reviewers_service.create_reviewer(
            db,
            review_session=review_session,
            name="Alice",
            email="not-an-email",
            user=user,
        )
    assert exc_info.value.code == "invalid_email"


def test_create_reviewer_rejects_duplicate_email_in_session(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )

    with pytest.raises(ReviewerOperationError) as exc_info:
        reviewers_service.create_reviewer(
            db,
            review_session=review_session,
            name="Alice 2",
            email="alice@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_email"


def test_create_reviewer_allows_same_email_across_sessions(
    db: Session,
) -> None:
    user, session_a = _seed(db, status="draft")
    session_b = ReviewSession(
        name="Other",
        code="reviewers-crud-other",
        created_by_user_id=user.id,
        status="draft",
    )
    db.add(session_b)
    db.flush()

    reviewers_service.create_reviewer(
        db,
        review_session=session_a,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    # Same email in a different session is fine.
    reviewers_service.create_reviewer(
        db,
        review_session=session_b,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )


# --------------------------------------------------------------------------- #
# update_reviewer
# --------------------------------------------------------------------------- #


def test_update_reviewer_emits_changes_envelope_for_changed_fields_only(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        tag_1="Mentor",
        user=user,
    )

    changes = reviewers_service.update_reviewer(
        db,
        reviewer=reviewer,
        name="Alice 2",
        email="alice@example.edu",  # unchanged → not in changes
        tag_1="Mentor",  # unchanged → not in changes
        tag_2="Cohort A",
        user=user,
    )

    assert set(changes.keys()) == {"name", "tag_2"}
    assert changes["name"] == ["Alice", "Alice 2"]
    assert changes["tag_2"] == [None, "Cohort A"]

    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "reviewer.updated")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event is not None
    assert set(event.detail["changes"].keys()) == {"name", "tag_2"}
    assert event.detail["refs"]["reviewer_id"] == reviewer.id


def test_update_reviewer_no_changes_emits_nothing(db: Session) -> None:
    user, review_session = _seed(db)
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    before = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewer.updated")
    ).all()

    changes = reviewers_service.update_reviewer(
        db,
        reviewer=reviewer,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    assert changes == {}

    after = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewer.updated")
    ).all()
    assert len(after) == len(before)


def test_update_reviewer_rejects_email_collision(db: Session) -> None:
    user, review_session = _seed(db)
    reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    bob = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Bob",
        email="bob@example.edu",
        user=user,
    )

    with pytest.raises(ReviewerOperationError) as exc_info:
        reviewers_service.update_reviewer(
            db,
            reviewer=bob,
            email="alice@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_email"


def test_update_reviewer_status_only_change_emits_reviewer_updated(
    db: Session,
) -> None:
    """Decision 13: inline-edit form always emits reviewer.updated,
    even for a status-only change. The bulk events stay reserved for
    the bulk-button path."""
    user, review_session = _seed(db)
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )

    changes = reviewers_service.update_reviewer(
        db,
        reviewer=reviewer,
        status="inactive",
        user=user,
    )
    assert changes == {"status": ["active", "inactive"]}

    bulk_event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reviewer.bulk_inactivated"
        )
    ).first()
    assert bulk_event is None  # the bulk path did not fire

    update_events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewer.updated")
    ).all()
    assert len(update_events) == 1


# --------------------------------------------------------------------------- #
# bulk_inactivate / bulk_reactivate
# --------------------------------------------------------------------------- #


def _seed_three_reviewers(
    db: Session,
) -> tuple[User, ReviewSession, list[Reviewer]]:
    user, review_session = _seed(db)
    rows = [
        reviewers_service.create_reviewer(
            db,
            review_session=review_session,
            name=f"R{i}",
            email=f"r{i}@example.edu",
            user=user,
        )
        for i in range(3)
    ]
    return user, review_session, rows


def test_bulk_inactivate_flips_only_active_rows(db: Session) -> None:
    user, review_session, rows = _seed_three_reviewers(db)
    rows[2].status = "inactive"  # already inactive
    db.flush()

    flipped = reviewers_service.bulk_inactivate(
        db,
        review_session=review_session,
        reviewer_ids=[r.id for r in rows],
        user=user,
    )

    assert sorted(flipped) == sorted([rows[0].id, rows[1].id])
    assert all(r.status == "inactive" for r in rows)

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reviewer.bulk_inactivated"
        )
    ).scalar_one()
    assert sorted(event.detail["snapshot"]["reviewer_ids"]) == sorted(flipped)


def test_bulk_reactivate_flips_only_inactive_rows(db: Session) -> None:
    user, review_session, rows = _seed_three_reviewers(db)
    for r in rows[:2]:
        r.status = "inactive"
    db.flush()

    flipped = reviewers_service.bulk_reactivate(
        db,
        review_session=review_session,
        reviewer_ids=[r.id for r in rows],
        user=user,
    )

    assert sorted(flipped) == sorted([rows[0].id, rows[1].id])
    assert all(r.status == "active" for r in rows)

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reviewer.bulk_reactivated"
        )
    ).scalar_one()
    assert sorted(event.detail["snapshot"]["reviewer_ids"]) == sorted(flipped)


def test_bulk_op_with_no_eligible_rows_emits_nothing(db: Session) -> None:
    user, review_session, rows = _seed_three_reviewers(db)
    # All three already active; bulk_inactivate has nothing to flip.
    flipped = reviewers_service.bulk_reactivate(
        db,
        review_session=review_session,
        reviewer_ids=[r.id for r in rows],
        user=user,
    )
    assert flipped == []

    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reviewer.bulk_reactivated"
        )
    ).all()
    assert events == []


def test_bulk_op_rejects_ids_outside_session(db: Session) -> None:
    user, session_a, rows_a = _seed_three_reviewers(db)
    session_b = ReviewSession(
        name="Other",
        code="reviewers-crud-other-bulk",
        created_by_user_id=user.id,
        status="draft",
    )
    db.add(session_b)
    db.flush()
    other = Reviewer(
        session_id=session_b.id, name="X", email="x@example.edu"
    )
    db.add(other)
    db.flush()

    with pytest.raises(ReviewerOperationError) as exc_info:
        reviewers_service.bulk_inactivate(
            db,
            review_session=session_a,
            reviewer_ids=[rows_a[0].id, other.id],
            user=user,
        )
    assert exc_info.value.code == "not_in_session"


def test_bulk_op_with_empty_id_list_is_no_op(db: Session) -> None:
    user, review_session, _ = _seed_three_reviewers(db)
    flipped = reviewers_service.bulk_inactivate(
        db,
        review_session=review_session,
        reviewer_ids=[],
        user=user,
    )
    assert flipped == []


# --------------------------------------------------------------------------- #
# Lifecycle gate: invalidate_if_validated
# --------------------------------------------------------------------------- #


def test_create_reviewer_invalidates_validated_session(db: Session) -> None:
    user, review_session = _seed(db, status="validated")

    reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    assert review_session.status == "draft"

    invalidate_event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.invalidated"
        )
    ).scalar_one()
    assert invalidate_event.detail["reason"] == "reviewer_created"


def test_update_reviewer_invalidates_validated_session(db: Session) -> None:
    user, review_session = _seed(db)
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    review_session.status = "validated"
    db.flush()

    reviewers_service.update_reviewer(
        db, reviewer=reviewer, name="Alice 2", user=user
    )
    assert review_session.status == "draft"


def test_no_op_update_does_not_invalidate(db: Session) -> None:
    user, review_session = _seed(db)
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        user=user,
    )
    review_session.status = "validated"
    db.flush()

    reviewers_service.update_reviewer(
        db, reviewer=reviewer, name="Alice", user=user
    )
    # Nothing changed → no invalidation.
    assert review_session.status == "validated"


def test_bulk_inactivate_invalidates_validated_session(db: Session) -> None:
    user, review_session, rows = _seed_three_reviewers(db)
    review_session.status = "validated"
    db.flush()

    reviewers_service.bulk_inactivate(
        db,
        review_session=review_session,
        reviewer_ids=[rows[0].id],
        user=user,
    )
    assert review_session.status == "draft"


def test_bulk_no_op_does_not_invalidate(db: Session) -> None:
    user, review_session, rows = _seed_three_reviewers(db)
    review_session.status = "validated"
    db.flush()

    # All rows are already active; bulk_reactivate has nothing to flip.
    reviewers_service.bulk_reactivate(
        db,
        review_session=review_session,
        reviewer_ids=[r.id for r in rows],
        user=user,
    )
    assert review_session.status == "validated"
