"""Integration coverage for the per-row reviewee CRUD service —
Segment 15F PR 4. Reviewee-side mirror of ``test_reviewers_crud``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Reviewee, ReviewSession, User
from app.services import reviewees as reviewees_service
from app.services.reviewees import RevieweeOperationError


def _seed(
    db: Session, *, status: str = "draft"
) -> tuple[User, ReviewSession]:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code=f"reviewees-crud-{status}",
        created_by_user_id=user.id,
        status=status,
    )
    db.add(review_session)
    db.flush()
    return user, review_session


# --------------------------------------------------------------------------- #
# create_reviewee
# --------------------------------------------------------------------------- #


def test_create_reviewee_inserts_row_and_emits_snapshot(
    db: Session,
) -> None:
    user, review_session = _seed(db)

    reviewee = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        profile_link="https://example.edu/carol",
        tag_1="Cohort A",
        user=user,
    )

    assert reviewee.id is not None
    assert reviewee.name == "Carol"
    assert reviewee.email_or_identifier == "carol@example.edu"
    assert reviewee.profile_link == "https://example.edu/carol"
    assert reviewee.status == "active"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewee.created")
    ).scalar_one()
    assert event.detail["snapshot"]["reviewee_id"] == reviewee.id
    assert event.detail["snapshot"]["email_or_identifier"] == "carol@example.edu"
    assert event.detail["snapshot"]["profile_link"] == (
        "https://example.edu/carol"
    )


def test_create_reviewee_accepts_non_email_identifier(
    db: Session,
) -> None:
    """Non-strict — a handle with no ``@`` is a valid identifier."""
    user, review_session = _seed(db)
    reviewee = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Dan",
        email_or_identifier="dan-2026",
        user=user,
    )
    assert reviewee.email_or_identifier == "dan-2026"


def test_create_reviewee_rejects_malformed_email_identifier(
    db: Session,
) -> None:
    """A value containing ``@`` must still be a valid email."""
    user, review_session = _seed(db)
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="Dan",
            email_or_identifier="dan@",
            user=user,
        )
    assert exc_info.value.code == "invalid_email"


def test_create_reviewee_rejects_empty_name(db: Session) -> None:
    user, review_session = _seed(db)
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="  ",
            email_or_identifier="x@example.edu",
            user=user,
        )
    assert exc_info.value.code == "empty_name"


def test_create_reviewee_rejects_empty_identifier(db: Session) -> None:
    user, review_session = _seed(db)
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="Dan",
            email_or_identifier="",
            user=user,
        )
    assert exc_info.value.code == "empty_identifier"


def test_create_reviewee_rejects_duplicate_identifier(db: Session) -> None:
    user, review_session = _seed(db)
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="Carol 2",
            email_or_identifier="carol@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_identifier"


def test_create_reviewee_rejects_case_variant_duplicate_email(
    db: Session,
) -> None:
    """Per-row dedup is case-insensitive for both email-shaped and
    anonymous identifiers, matching CSV import behavior (P0.1 in
    ``guide/weaknesses_and_bugs_found_by_codex.md``)."""
    user, review_session = _seed(db)
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="Carol@example.edu",
        user=user,
    )
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="Carol 2",
            email_or_identifier="carol@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_identifier"


def test_create_reviewee_rejects_case_variant_anonymous_identifier(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Token holder",
        email_or_identifier="Token-AB",
        user=user,
    )
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name="Other holder",
            email_or_identifier="token-ab",
            user=user,
        )
    assert exc_info.value.code == "duplicate_identifier"


# --------------------------------------------------------------------------- #
# update_reviewee
# --------------------------------------------------------------------------- #


def test_update_reviewee_emits_changes_for_changed_fields_only(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    reviewee = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )

    changes = reviewees_service.update_reviewee(
        db,
        reviewee=reviewee,
        name="Carol Renamed",
        email_or_identifier="carol@example.edu",  # unchanged
        profile_link="https://example.edu/c",
        user=user,
    )
    assert set(changes.keys()) == {"name", "profile_link"}

    event = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "reviewee.updated")
            .order_by(AuditEvent.id.desc())
        )
        .scalars()
        .first()
    )
    assert event is not None
    assert event.detail["refs"]["reviewee_id"] == reviewee.id


def test_update_reviewee_no_changes_emits_nothing(db: Session) -> None:
    user, review_session = _seed(db)
    reviewee = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )
    changes = reviewees_service.update_reviewee(
        db,
        reviewee=reviewee,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )
    assert changes == {}
    assert (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "reviewee.updated"
            )
        ).first()
        is None
    )


def test_update_reviewee_rejects_identifier_collision(db: Session) -> None:
    user, review_session = _seed(db)
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )
    dan = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Dan",
        email_or_identifier="dan-2026",
        user=user,
    )
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.update_reviewee(
            db,
            reviewee=dan,
            email_or_identifier="carol@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_identifier"


def test_update_reviewee_rejects_case_variant_identifier_collision(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="Carol@example.edu",
        user=user,
    )
    dan = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Dan",
        email_or_identifier="dan-2026",
        user=user,
    )
    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.update_reviewee(
            db,
            reviewee=dan,
            email_or_identifier="carol@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_identifier"


# --------------------------------------------------------------------------- #
# bulk_inactivate / bulk_reactivate
# --------------------------------------------------------------------------- #


def _seed_three(
    db: Session,
) -> tuple[User, ReviewSession, list[Reviewee]]:
    user, review_session = _seed(db)
    rows = [
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name=f"E{i}",
            email_or_identifier=f"e{i}@example.edu",
            user=user,
        )
        for i in range(3)
    ]
    return user, review_session, rows


def test_bulk_inactivate_flips_only_active_rows(db: Session) -> None:
    user, review_session, rows = _seed_three(db)
    rows[2].status = "inactive"
    db.flush()

    flipped = reviewees_service.bulk_inactivate(
        db,
        review_session=review_session,
        reviewee_ids=[r.id for r in rows],
        user=user,
    )
    assert sorted(flipped) == sorted([rows[0].id, rows[1].id])
    assert all(r.status == "inactive" for r in rows)

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reviewee.bulk_inactivated"
        )
    ).scalar_one()
    assert sorted(event.detail["snapshot"]["reviewee_ids"]) == sorted(flipped)


def test_bulk_reactivate_flips_only_inactive_rows(db: Session) -> None:
    user, review_session, rows = _seed_three(db)
    for r in rows[:2]:
        r.status = "inactive"
    db.flush()

    flipped = reviewees_service.bulk_reactivate(
        db,
        review_session=review_session,
        reviewee_ids=[r.id for r in rows],
        user=user,
    )
    assert sorted(flipped) == sorted([rows[0].id, rows[1].id])
    assert all(r.status == "active" for r in rows)


def test_bulk_op_rejects_ids_outside_session(db: Session) -> None:
    user, session_a, rows_a = _seed_three(db)
    session_b = ReviewSession(
        name="Other",
        code="reviewees-crud-other",
        created_by_user_id=user.id,
        status="draft",
    )
    db.add(session_b)
    db.flush()
    other = Reviewee(
        session_id=session_b.id, name="X", email_or_identifier="x@example.edu"
    )
    db.add(other)
    db.flush()

    with pytest.raises(RevieweeOperationError) as exc_info:
        reviewees_service.bulk_inactivate(
            db,
            review_session=session_a,
            reviewee_ids=[rows_a[0].id, other.id],
            user=user,
        )
    assert exc_info.value.code == "not_in_session"


# --------------------------------------------------------------------------- #
# Lifecycle gate.
# --------------------------------------------------------------------------- #


def test_create_reviewee_invalidates_validated_session(db: Session) -> None:
    user, review_session = _seed(db, status="validated")
    reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )
    assert review_session.status == "draft"


def test_no_op_update_does_not_invalidate(db: Session) -> None:
    user, review_session = _seed(db)
    reviewee = reviewees_service.create_reviewee(
        db,
        review_session=review_session,
        name="Carol",
        email_or_identifier="carol@example.edu",
        user=user,
    )
    review_session.status = "validated"
    db.flush()
    reviewees_service.update_reviewee(
        db, reviewee=reviewee, name="Carol", user=user
    )
    assert review_session.status == "validated"
