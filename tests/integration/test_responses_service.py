from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentResponseField,
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
        correlation_id="c1",
    )

    assert result.submitted is False
    assert result.submitted_count == 0
    assert any(m.field_key == "rating" for m in result.missing)
    assert result.missing[0].reviewee_name == "Carol"
    # PR ε — every MissingPosition entry carries the page number the
    # reviewer needs to navigate to. ``_seed`` builds a single-
    # instrument session, so all entries land at Page 1.
    assert all(m.position == 1 for m in result.missing)


def test_reviewer_session_state_no_assignments(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    # Drop the only assignment — reviewer is left with no active rows.
    assignment.include = False
    db.flush()

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )

    assert state.total_assignments == 0
    assert state.completed_count == 0
    assert state.missing_required_count == 0
    assert state.pill_state == "not started"


def test_reviewer_session_state_no_responses_yet(db: Session) -> None:
    op, reviewer, review_session, _ = _seed(db)

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )

    assert state.total_assignments == 1
    assert state.completed_count == 0
    # The default instrument has one required field ("rating").
    assert state.missing_required_count == 1
    assert state.pill_state == "not started"


def test_reviewer_session_state_draft_in_progress(db: Session) -> None:
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

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )

    # All required fields are filled but never submitted.
    assert state.total_assignments == 1
    assert state.completed_count == 1
    assert state.missing_required_count == 0
    assert state.pill_state == "in progress"


def test_reviewer_session_state_submitted(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="4"),
        ],
        correlation_id="c1",
    )

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )

    assert state.total_assignments == 1
    assert state.completed_count == 1
    assert state.missing_required_count == 0
    assert state.pill_state == "submitted"


def test_reviewer_session_state_no_required_field_draft_is_in_progress(
    db: Session,
) -> None:
    """An instrument with only optional fields: a saved-but-not-
    submitted draft rolls up as "in progress", not "submitted".
    Regression — the submitted check was gated on required fields,
    so a no-required instrument's drafts were mis-flagged submitted."""
    op, reviewer, review_session, assignment = _seed(db)
    # Make every field on the (default) instrument optional.
    for field in db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == assignment.instrument_id
        )
    ).scalars():
        field.required = False
    db.flush()

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

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    assert state.pill_state == "in progress"


def test_reviewer_session_state_session_pill_projection(db: Session) -> None:
    """``session_pill_for_reviewer`` is now a thin projection of
    ``reviewer_session_state``. Verify they agree end-to-end."""
    op, reviewer, review_session, assignment = _seed(db)
    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="3"),
        ],
        correlation_id="c1",
    )

    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    pill = responses_service.session_pill_for_reviewer(
        db, reviewer=reviewer, session_id=review_session.id
    )

    assert pill.state == state.pill_state
    assert pill.total_assignments == state.total_assignments
    assert pill.completed_rows == state.completed_count
