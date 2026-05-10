"""Service-layer ``validated → draft`` invariant tests.

PR for items #3 + #16 moved the ``_invalidate_if_validated`` policy
from ``routes_operator.py`` into the mutating services themselves.
These tests pin the invariant at the service layer so a future
refactor can't silently regress: every setup-mutating service must
flip a ``validated`` session back to ``draft``, and the two
visibility-when-closed surfaces must NOT (item #16).
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.schemas.assignments import AssignmentMode
from app.schemas.imports import ReviewerImportRow
from app.schemas.sessions import SessionCreate
from app.services import (
    assignments as assignments_service,
    csv_imports,
    instruments as instruments_service,
    session_lifecycle as lifecycle,
    sessions as sessions_service,
)


def _seed_validated() -> "tuple[User, Reviewer, Reviewee, ReviewSession]":
    raise NotImplementedError("see ``_setup`` fixture below")


@pytest.fixture
def setup(
    db: Session,
) -> "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]":
    op = User(email="op@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="spring-2026", created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    db.add(SessionOperator(session_id=review_session.id, user_id=op.id, role="owner"))
    instrument = instruments_service.ensure_default_instrument(db, review_session)
    reviewer = Reviewer(
        session_id=review_session.id, name="Rae", email="rae@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    db.add(reviewer)
    db.add(reviewee)
    db.flush()
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    review_session.status = lifecycle.SessionStatus.validated.value
    db.flush()
    return op, review_session, reviewer, reviewee, assignment


# -- Pure helper invariants --------------------------------------------------


def test_invalidate_if_validated_flips_validated_to_draft(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=op, reason="probe"
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_invalidate_if_validated_is_noop_on_draft(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    """Idempotency: a second call (or a service that calls multiple
    mutating sub-services in one request) must not raise."""
    op, review_session, *_ = setup
    review_session.status = "draft"
    db.flush()

    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=op, reason="probe"
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


# -- Mutating services flip validated → draft -------------------------------


def test_session_update_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    sessions_service.update_session(
        db,
        review_session=review_session,
        user=op,
        payload=SessionCreate(
            name="Renamed",
            code=review_session.code,
            description=None,
            deadline=None,
        ),
        correlation_id="c1",
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_csv_save_reviewers_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    csv_imports.save_reviewers(
        db,
        session=review_session,
        user=op,
        rows=[ReviewerImportRow(name="Sam", email="sam@example.edu")],
        filename="r.csv",
        correlation_id="c1",
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_csv_delete_all_reviewees_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    csv_imports.delete_all_reviewees(
        db,
        review_session=review_session,
        user=op,
        correlation_id="c1",
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_assignments_replace_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, reviewer, reviewee, _ = setup

    assignments_service.replace_assignments(
        db,
        review_session=review_session,
        user=op,
        pairs=[(reviewer, reviewee)],
        mode=AssignmentMode.rule_based,
        correlation_id="c1",
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_assignments_delete_all_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    assignments_service.delete_all_assignments(
        db,
        review_session=review_session,
        user=op,
        correlation_id="c1",
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_instrument_create_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    instruments_service.create_instrument(
        db, review_session=review_session, after_instrument_id=None, actor=op
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_instrument_update_description_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, _, _, assignment = setup
    instrument = assignment.instrument

    instruments_service.update_instrument_description(
        db, instrument=instrument, description="updated", actor=op
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_response_field_add_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, _, _, assignment = setup
    instrument = assignment.instrument

    instruments_service.add_default_response_field(
        db, instrument=instrument, actor=op
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_response_type_add_invalidates(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    instruments_service.add_response_type_definition(
        db,
        review_session=review_session,
        response_type="Custom",
        data_type="Integer",
        min=1,
        max=10,
        step=1,
        list_csv=None,
        actor=op,
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


# -- #16: visibility services must NOT invalidate ---------------------------


def test_bulk_set_visibility_does_not_invalidate(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, *_ = setup

    instruments_service.bulk_set_visibility(
        db, review_session=review_session, target=True, actor=op
    )

    db.refresh(review_session)
    assert review_session.status == "validated"


def test_set_responses_visible_when_closed_does_not_invalidate(
    setup: "tuple[User, ReviewSession, Reviewer, Reviewee, Assignment]",
    db: Session,
) -> None:
    op, review_session, _, _, assignment = setup
    instrument = assignment.instrument

    lifecycle.set_responses_visible_when_closed(
        db,
        instrument=instrument,
        review_session=review_session,
        user=op,
        visible=True,
    )

    db.refresh(review_session)
    assert review_session.status == "validated"
