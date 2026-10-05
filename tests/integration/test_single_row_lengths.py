"""The single-row Add / Edit forms and the friendly-label editor refuse a
value longer than its column (findings Cc3, 2026-10-05).

The CSV importers have checked every cell against the model's declared
``String(n)`` since #2830; the per-row services and the label editor
wrote straight through, so on Postgres an over-long value answered 500
at flush. Each service now raises its ``too_long`` operation error,
which the routes render like any other refusal, and the label save
answers 422 before writing any slot.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionFieldLabel,
    User,
)
from app.services import observers, relationships, reviewees, reviewers

LONG = "x" * 256


def _seed(db: Session) -> tuple[User, ReviewSession]:
    user = User(email="op-cc3@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    rs = ReviewSession(name="Cc3", code="cc3", created_by_user_id=user.id)
    db.add(rs)
    db.flush()
    return user, rs


def test_reviewer_create_and_update_refuse_an_over_long_value(
    db: Session,
) -> None:
    user, rs = _seed(db)
    with pytest.raises(reviewers.ReviewerOperationError) as exc:
        reviewers.create_reviewer(
            db, review_session=rs, name=LONG, email="a@x.edu", user=user
        )
    assert exc.value.code == "too_long"
    assert exc.value.message == "Name is 256 characters; at most 255 fit."

    reviewer = reviewers.create_reviewer(
        db, review_session=rs, name="Al", email="a@x.edu", user=user
    )
    with pytest.raises(reviewers.ReviewerOperationError) as exc:
        reviewers.update_reviewer(
            db, reviewer=reviewer, profile_link="h" * 2001, user=user
        )
    assert exc.value.code == "too_long"
    assert "Profile link is 2001 characters" in exc.value.message


def test_reviewee_create_and_update_refuse_an_over_long_value(
    db: Session,
) -> None:
    user, rs = _seed(db)
    with pytest.raises(reviewees.RevieweeOperationError) as exc:
        reviewees.create_reviewee(
            db,
            review_session=rs,
            name="Bo",
            email_or_identifier="b@x.edu",
            tag_2=LONG,
            user=user,
        )
    assert exc.value.code == "too_long"
    assert exc.value.message.startswith("Tag 2 is 256 characters")

    reviewee = reviewees.create_reviewee(
        db, review_session=rs, name="Bo", email_or_identifier="b@x.edu", user=user
    )
    with pytest.raises(reviewees.RevieweeOperationError) as exc:
        reviewees.update_reviewee(db, reviewee=reviewee, name=LONG, user=user)
    assert exc.value.code == "too_long"


def test_observer_create_and_update_refuse_an_over_long_value(
    db: Session,
) -> None:
    user, rs = _seed(db)
    with pytest.raises(observers.ObserverOperationError) as exc:
        observers.create_observer(
            db,
            review_session=rs,
            email="o@x.edu",
            display_name=LONG,
            user=user,
        )
    assert exc.value.code == "too_long"

    observer = observers.create_observer(
        db, review_session=rs, email="o@x.edu", user=user
    )
    with pytest.raises(observers.ObserverOperationError) as exc:
        observers.update_observer(db, observer=observer, tag_1=LONG, user=user)
    assert exc.value.code == "too_long"


def test_relationship_create_and_update_refuse_an_over_long_tag(
    db: Session,
) -> None:
    user, rs = _seed(db)
    rvr = Reviewer(session_id=rs.id, name="R", email="r@x.edu")
    rve = Reviewee(session_id=rs.id, name="E", email_or_identifier="e@x.edu")
    db.add_all([rvr, rve])
    db.flush()
    with pytest.raises(relationships.RelationshipOperationError) as exc:
        relationships.create_relationship(
            db,
            review_session=rs,
            reviewer_id=rvr.id,
            reviewee_id=rve.id,
            tag_3=LONG,
            user=user,
        )
    assert exc.value.code == "too_long"

    rel = relationships.create_relationship(
        db, review_session=rs, reviewer_id=rvr.id, reviewee_id=rve.id, user=user
    )
    with pytest.raises(relationships.RelationshipOperationError) as exc:
        relationships.update_relationship(
            db, relationship=rel, tag_1=LONG, user=user
        )
    assert exc.value.code == "too_long"


def test_the_add_row_renders_the_refusal(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Cc3 Add", "code": "cc3-add"},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "cc3-add")
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{rs.id}/reviewers/create",
        data={"name": LONG, "email": "a@x.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Name is 256 characters; at most 255 fit." in response.text
    assert db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).first() is None


def test_the_label_editor_refuses_an_over_long_label_whole(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Cc3 Labels", "code": "cc3-labels"},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "cc3-labels")
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{rs.id}/reviewers/field-labels",
        data={"tag_1": "Cohort", "tag_2": LONG, "tag_3": ""},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "256 characters; at most 255 fit" in response.text
    # Checked before any slot is written: the valid Tag 1 did not land.
    assert db.execute(
        select(SessionFieldLabel).where(SessionFieldLabel.session_id == rs.id)
    ).first() is None
