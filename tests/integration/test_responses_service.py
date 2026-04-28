from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services.instruments import ensure_default_instrument


def _seed(db: Session) -> tuple[User, Reviewer, ReviewSession, Assignment]:
    op = User(email="op@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="spring-2026", created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    db.add(SessionOperator(session_id=review_session.id, user_id=op.id, role="owner"))
    instrument = ensure_default_instrument(db, review_session)
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
    return op, reviewer, review_session, assignment


def test_parse_form_payload_extracts_response_entries() -> None:
    upserts = responses_service.parse_form_payload(
        {
            "response[1][rating]": "4",
            "response[1][comments]": "good",
            "response[2][rating]": "  ",
            "irrelevant": "ignore",
        }
    )

    by_key = {(u.assignment_id, u.field_key): u.value for u in upserts}
    assert by_key[(1, "rating")] == "4"
    assert by_key[(1, "comments")] == "good"
    assert by_key[(2, "rating")] == ""  # whitespace normalised to empty


def test_save_draft_with_no_upserts_writes_zero(db: Session) -> None:
    op, reviewer, review_session, _ = _seed(db)

    result = responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[],
        correlation_id="corr",
    )

    assert result.upsert_count == 0


def test_save_draft_upserts_then_updates(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)

    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="3"),
        ],
        correlation_id="corr-1",
    )
    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="5"),
        ],
        correlation_id="corr-2",
    )

    is_complete, missing, _ = responses_service.compute_row_completion(db, assignment)
    assert is_complete is True
    assert missing == 0


def test_save_draft_empty_value_deletes_existing_row(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)

    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="4"),
        ],
        correlation_id="c1",
    )
    is_complete, _, _ = responses_service.compute_row_completion(db, assignment)
    assert is_complete is True

    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value=""),
        ],
        correlation_id="c2",
    )
    is_complete, missing, _ = responses_service.compute_row_completion(db, assignment)
    assert is_complete is False
    assert missing == 1


def test_compute_row_completion_marks_required_only(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    # rating is required, comments is optional. Provide only comments.
    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(
                assignment_id=assignment.id, field_key="comments", value="hi"
            ),
        ],
        correlation_id="c1",
    )
    is_complete, missing, submitted = responses_service.compute_row_completion(
        db, assignment
    )
    assert is_complete is False
    assert missing == 1
    assert submitted is None


def test_submit_missing_required_returns_warning_without_audit(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)

    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[],
        acknowledge_missing=False,
        correlation_id="c1",
    )

    assert result.submitted is False
    assert result.submitted_count == 0
    assert any(m.field_key == "rating" for m in result.missing)
    assert result.missing[0].reviewee_name == "Carol"
