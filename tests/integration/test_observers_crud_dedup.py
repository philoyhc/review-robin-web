"""Case-insensitive duplicate-email coverage for the per-row observer
CRUD service. Mirrors the reviewer / reviewee dedup tests for P0.1 in
``guide/archive/weaknesses_and_bugs_found_by_codex.md``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import observers as observers_service
from app.services.observers import ObserverOperationError


def _seed(db: Session) -> tuple[User, ReviewSession]:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code="observers-crud-dedup",
        created_by_user_id=user.id,
        status="draft",
    )
    db.add(review_session)
    db.flush()
    return user, review_session


def test_create_observer_rejects_case_variant_duplicate_email(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    observers_service.create_observer(
        db,
        review_session=review_session,
        email="Watcher@example.edu",
        user=user,
    )

    with pytest.raises(ObserverOperationError) as exc_info:
        observers_service.create_observer(
            db,
            review_session=review_session,
            email="watcher@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_email"


def test_update_observer_rejects_case_variant_email_collision(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    observers_service.create_observer(
        db,
        review_session=review_session,
        email="Watcher@example.edu",
        user=user,
    )
    other = observers_service.create_observer(
        db,
        review_session=review_session,
        email="other@example.edu",
        user=user,
    )

    with pytest.raises(ObserverOperationError) as exc_info:
        observers_service.update_observer(
            db,
            observer=other,
            email="watcher@example.edu",
            user=user,
        )
    assert exc_info.value.code == "duplicate_email"
