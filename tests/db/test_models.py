from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Invitation,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)


def _make_user(db: Session, email: str = "operator@example.edu") -> User:
    user = User(email=email, display_name="Operator")
    db.add(user)
    db.flush()
    return user


def _make_session(db: Session, user: User, code: str = "SESS-001") -> ReviewSession:
    review = ReviewSession(
        name="Spring Review",
        code=code,
        description="Spring review cycle.",
        status="draft",
        created_by_user_id=user.id,
    )
    db.add(review)
    db.flush()
    db.add(SessionOperator(session_id=review.id, user_id=user.id, role="owner"))
    db.flush()
    return review


def test_can_create_a_user(db: Session) -> None:
    user = _make_user(db)

    fetched = db.scalars(select(User).where(User.email == "operator@example.edu")).one()
    assert fetched.id == user.id
    assert fetched.display_name == "Operator"
    assert fetched.created_at is not None


def test_can_create_a_session_owned_by_a_user(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)

    refreshed = db.scalars(
        select(ReviewSession).where(ReviewSession.code == "SESS-001")
    ).one()
    assert refreshed.created_by_user_id == user.id
    assert refreshed.created_by_user.email == "operator@example.edu"
    assert len(refreshed.operators) == 1
    assert refreshed.operators[0].role == "owner"


def test_can_add_reviewer_and_reviewee_to_a_session(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)

    reviewer = Reviewer(
        session_id=review.id, name="Alice Reviewer", email="alice@example.edu"
    )
    reviewee = Reviewee(
        session_id=review.id,
        name="Bob Reviewee",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()

    db.refresh(review)
    assert {r.email for r in review.reviewers} == {"alice@example.edu"}
    assert {r.email_or_identifier for r in review.reviewees} == {"bob@example.edu"}


def test_can_add_an_instrument_with_display_and_response_fields(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)

    instrument = Instrument(session_id=review.id, name="General review", order=0)
    db.add(instrument)
    db.flush()

    from app.services.instruments import (
        ensure_default_response_type_definitions,
    )

    rtds = ensure_default_response_type_definitions(db, review)
    db.add_all(
        [
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="Reviewee name",
                source_type="reviewee",
                source_field="name",
                order=0,
            ),
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key="rating",
                label="Rating (1-5)",
                response_type_id=rtds["1-to-5int"].id,
                required=True,
                order=0,
                validation={"min": 1, "max": 5},
            ),
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key="comments",
                label="Comments",
                response_type_id=rtds["Long_text"].id,
                required=False,
                order=1,
            ),
        ]
    )
    db.flush()

    refreshed = db.scalars(
        select(Instrument).where(Instrument.id == instrument.id)
    ).one()
    assert len(refreshed.display_fields) == 1
    assert len(refreshed.response_fields) == 2
    rating = next(f for f in refreshed.response_fields if f.field_key == "rating")
    assert rating.required is True
    assert rating.validation == {"min": 1, "max": 5}


def test_can_create_an_assignment_linking_reviewer_reviewee_instrument(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)
    reviewer = Reviewer(
        session_id=review.id, name="Alice", email="alice@example.edu"
    )
    reviewee = Reviewee(
        session_id=review.id, name="Bob", email_or_identifier="bob@example.edu"
    )
    instrument = Instrument(session_id=review.id, name="General review")
    db.add_all([reviewer, reviewee, instrument])
    db.flush()

    assignment = Assignment(
        session_id=review.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        created_by_mode="manual",
    )
    db.add(assignment)
    db.flush()

    fetched = db.scalars(select(Assignment).where(Assignment.id == assignment.id)).one()
    assert fetched.reviewer.email == "alice@example.edu"
    assert fetched.reviewee.email_or_identifier == "bob@example.edu"
    assert fetched.instrument.name == "General review"
    assert fetched.include is True


def test_can_create_a_response_for_an_assignment_field(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)
    reviewer = Reviewer(session_id=review.id, name="A", email="a@example.edu")
    reviewee = Reviewee(session_id=review.id, name="B", email_or_identifier="b@example.edu")
    instrument = Instrument(session_id=review.id, name="I")
    db.add_all([reviewer, reviewee, instrument])
    db.flush()

    from app.services.instruments import (
        ensure_default_response_type_definitions,
    )
    rtds = ensure_default_response_type_definitions(db, review)
    response_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="rating",
        label="Rating",
        response_type_id=rtds["1-to-5int"].id,
        required=True,
    )
    db.add(response_field)
    db.flush()

    assignment = Assignment(
        session_id=review.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()

    response = Response(
        assignment_id=assignment.id,
        response_field_id=response_field.id,
        value="4",
        submitted_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    db.add(response)
    db.flush()

    fetched = db.scalars(select(Response).where(Response.id == response.id)).one()
    assert fetched.value == "4"
    assert fetched.assignment_id == assignment.id
    assert fetched.response_field.field_key == "rating"
    assert fetched.version == 1


def test_can_create_an_invitation_for_a_reviewer(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)
    reviewer = Reviewer(session_id=review.id, name="A", email="a@example.edu")
    db.add(reviewer)
    db.flush()

    invitation = Invitation(
        session_id=review.id,
        reviewer_id=reviewer.id,
        token_hash="hashed-token-1",
        status="pending",
    )
    db.add(invitation)
    db.flush()

    fetched = db.scalars(
        select(Invitation).where(Invitation.token_hash == "hashed-token-1")
    ).one()
    assert fetched.reviewer.email == "a@example.edu"
    assert fetched.status == "pending"


def test_can_write_an_audit_event(db: Session) -> None:
    user = _make_user(db)
    review = _make_session(db, user)

    event = AuditEvent(
        session_id=review.id,
        actor_user_id=user.id,
        event_type="session.created",
        severity="info",
        summary="Session SESS-001 created",
        detail={"session_code": "SESS-001"},
        correlation_id="corr-1",
    )
    db.add(event)
    db.flush()

    fetched = db.scalars(
        select(AuditEvent).where(AuditEvent.correlation_id == "corr-1")
    ).one()
    assert fetched.event_type == "session.created"
    assert fetched.severity == "info"
    assert fetched.detail == {"session_code": "SESS-001"}
    assert fetched.session is not None
    assert fetched.actor is not None and fetched.actor.email == "operator@example.edu"
