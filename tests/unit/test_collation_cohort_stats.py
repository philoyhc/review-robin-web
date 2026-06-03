"""Unit tests for
``app.services.collation.build_cohort_stats_for_instrument``.

Pins the per-instrument cohort aggregation shape: both rows
share an identical aggregate over the in-cohort assignment pool,
they differ in ``distinct_count`` only (per-side headcount
badge), only submitted responses count, and the empty-pool
branch returns a uniform all-empty shape so the surface
template doesn't need a special case.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.collation import build_cohort_stats_for_instrument
from app.services.observer_cohort import CohortAssignments


def _make_session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    sess = ReviewSession(
        name="Sess",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(sess)
    db.flush()
    return sess


def _make_instrument(
    db: Session, sess: ReviewSession, *, name: str = "Instrument 1"
) -> Instrument:
    inst = Instrument(session_id=sess.id, name=name, order=0)
    db.add(inst)
    db.flush()
    return inst


def _make_field(
    db: Session,
    instrument: Instrument,
    *,
    field_key: str,
    data_type: str,
    label: str | None = None,
    order: int = 0,
    list_csv: str | None = None,
) -> InstrumentResponseField:
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label or field_key,
        _inline_data_type=data_type,
        required=False,
        order=order,
        _inline_list_csv=list_csv,
    )
    db.add(field)
    db.flush()
    return field


def _make_reviewer(
    db: Session, sess: ReviewSession, *, name: str, email: str
) -> Reviewer:
    r = Reviewer(session_id=sess.id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _make_reviewee(
    db: Session, sess: ReviewSession, *, name: str, email: str
) -> Reviewee:
    r = Reviewee(session_id=sess.id, name=name, email_or_identifier=email)
    db.add(r)
    db.flush()
    return r


def _make_assignment(
    db: Session,
    sess: ReviewSession,
    instrument: Instrument,
    reviewer: Reviewer,
    reviewee: Reviewee,
) -> Assignment:
    a = Assignment(
        session_id=sess.id,
        instrument_id=instrument.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(a)
    db.flush()
    return a


def _submit_response(
    db: Session,
    assignment: Assignment,
    field: InstrumentResponseField,
    value: str,
    *,
    submitted: bool = True,
) -> None:
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value=value,
            submitted_at=(
                datetime.now(timezone.utc) if submitted else None
            ),
        )
    )


def test_empty_pool_returns_empty_rows_shaped_to_fields(
    db: Session,
) -> None:
    sess = _make_session(db, code="stats-empty")
    inst = _make_instrument(db, sess)
    _make_field(db, inst, field_key="rating", data_type="Integer")
    _make_field(db, inst, field_key="comments", data_type="String", order=1)
    db.refresh(inst)

    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db,
        instrument=inst,
        cohort=CohortAssignments(
            assignment_ids=frozenset(),
            distinct_reviewer_count=0,
            distinct_reviewee_count=0,
        ),
    )
    assert reviewer_row.distinct_count == 0
    assert reviewee_row.distinct_count == 0
    assert reviewer_row.response_count == 0
    assert reviewee_row.response_count == 0
    assert len(reviewer_row.field_cells) == 2
    assert reviewer_row.field_cells[0].data_type == "Integer"
    assert reviewer_row.field_cells[1].data_type == "String"


def test_both_rows_share_aggregate_differ_only_in_distinct_count(
    db: Session,
) -> None:
    """Two reviewers reviewing one reviewee → 2 reviewers,
    1 reviewee. Both rows aggregate the same two responses; only
    the headcount badge differs."""
    sess = _make_session(db, code="stats-share")
    inst = _make_instrument(db, sess)
    rating = _make_field(db, inst, field_key="rating", data_type="Integer")
    db.refresh(inst)

    r1 = _make_reviewer(db, sess, name="R1", email="r1@x")
    r2 = _make_reviewer(db, sess, name="R2", email="r2@x")
    e1 = _make_reviewee(db, sess, name="E1", email="e1@x")
    a1 = _make_assignment(db, sess, inst, r1, e1)
    a2 = _make_assignment(db, sess, inst, r2, e1)
    _submit_response(db, a1, rating, "4")
    _submit_response(db, a2, rating, "6")
    db.commit()

    cohort = CohortAssignments(
        assignment_ids=frozenset({a1.id, a2.id}),
        distinct_reviewer_count=2,
        distinct_reviewee_count=1,
    )
    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    # Headcounts differ.
    assert reviewer_row.distinct_count == 2
    assert reviewee_row.distinct_count == 1
    # Same aggregate on both sides.
    assert reviewer_row.response_count == reviewee_row.response_count == 2
    assert (
        reviewer_row.field_cells[0].average
        == reviewee_row.field_cells[0].average
        == 5.0
    )


def test_assignments_outside_pool_are_excluded(db: Session) -> None:
    """An assignment whose id isn't in the pool doesn't
    contribute, even if its reviewer/reviewee otherwise would."""
    sess = _make_session(db, code="stats-pool-bound")
    inst = _make_instrument(db, sess)
    rating = _make_field(db, inst, field_key="rating", data_type="Integer")
    db.refresh(inst)

    r1 = _make_reviewer(db, sess, name="R1", email="r1@x")
    e1 = _make_reviewee(db, sess, name="E1", email="e1@x")
    e2 = _make_reviewee(db, sess, name="E2", email="e2@x")
    a_in = _make_assignment(db, sess, inst, r1, e1)
    a_out = _make_assignment(db, sess, inst, r1, e2)
    _submit_response(db, a_in, rating, "4")
    _submit_response(db, a_out, rating, "9")
    db.commit()

    cohort = CohortAssignments(
        assignment_ids=frozenset({a_in.id}),
        distinct_reviewer_count=1,
        distinct_reviewee_count=1,
    )
    reviewer_row, _ = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    # Only a_in's "4" feeds the average; a_out's "9" is outside the pool.
    assert reviewer_row.response_count == 1
    assert reviewer_row.field_cells[0].average == 4.0


def test_only_submitted_responses_count(db: Session) -> None:
    """Draft responses (``submitted_at IS NULL``) are excluded
    even when their assignment is in the pool."""
    sess = _make_session(db, code="stats-submit-only")
    inst = _make_instrument(db, sess)
    rating = _make_field(db, inst, field_key="rating", data_type="Integer")
    db.refresh(inst)

    r1 = _make_reviewer(db, sess, name="R1", email="r1@x")
    e1 = _make_reviewee(db, sess, name="E1", email="e1@x")
    e2 = _make_reviewee(db, sess, name="E2", email="e2@x")
    a1 = _make_assignment(db, sess, inst, r1, e1)
    a2 = _make_assignment(db, sess, inst, r1, e2)
    _submit_response(db, a1, rating, "4", submitted=True)
    _submit_response(db, a2, rating, "9", submitted=False)
    db.commit()

    cohort = CohortAssignments(
        assignment_ids=frozenset({a1.id, a2.id}),
        distinct_reviewer_count=1,
        distinct_reviewee_count=2,
    )
    reviewer_row, _ = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    assert reviewer_row.response_count == 1
    assert reviewer_row.field_cells[0].average == 4.0


def test_field_cells_in_field_order_match_per_row(db: Session) -> None:
    """Reviewer and reviewee rows must line up column-by-column."""
    sess = _make_session(db, code="stats-order")
    inst = _make_instrument(db, sess)
    _make_field(db, inst, field_key="z_last", data_type="String", order=2)
    _make_field(db, inst, field_key="a_first", data_type="Integer", order=0)
    _make_field(db, inst, field_key="m_mid", data_type="String", order=1)
    db.refresh(inst)

    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db,
        instrument=inst,
        cohort=CohortAssignments(
            assignment_ids=frozenset(),
            distinct_reviewer_count=0,
            distinct_reviewee_count=0,
        ),
    )
    types_reviewer = [c.data_type for c in reviewer_row.field_cells]
    types_reviewee = [c.data_type for c in reviewee_row.field_cells]
    assert types_reviewer == types_reviewee
    # ``order`` field drives the sequence.
    assert types_reviewer == ["Integer", "String", "String"]


def test_empty_cells_for_fields_with_no_data(db: Session) -> None:
    sess = _make_session(db, code="stats-mixed")
    inst = _make_instrument(db, sess)
    rating = _make_field(db, inst, field_key="rating", data_type="Integer")
    notes = _make_field(
        db, inst, field_key="notes", data_type="String", order=1
    )
    db.refresh(inst)

    r1 = _make_reviewer(db, sess, name="R1", email="r1@x")
    e1 = _make_reviewee(db, sess, name="E1", email="e1@x")
    a1 = _make_assignment(db, sess, inst, r1, e1)
    _submit_response(db, a1, rating, "5")
    _submit_response(db, a1, notes, "")
    db.commit()

    cohort = CohortAssignments(
        assignment_ids=frozenset({a1.id}),
        distinct_reviewer_count=1,
        distinct_reviewee_count=1,
    )
    reviewer_row, _ = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    assert reviewer_row.field_cells[0].response_count == 1
    assert reviewer_row.field_cells[1].response_count == 0
    assert reviewer_row.response_count == 1
