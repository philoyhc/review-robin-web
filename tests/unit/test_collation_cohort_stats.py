"""Unit tests for
``app.services.collation.build_cohort_stats_for_instrument``.

Pins the per-instrument cohort aggregation shape — both rows
(reviewer / reviewee) line up column-by-column, only submitted
responses count, and the empty-side branch returns a uniform
all-empty shape so the surface template doesn't need a special
case.
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
from app.services.observer_cohort import CohortIds


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
    # ``data_type`` is a property fronted by ``_inline_data_type``;
    # construct via the underlying column.
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


def test_empty_cohort_returns_empty_rows_shaped_to_fields(
    db: Session,
) -> None:
    sess = _make_session(db, code="stats-empty")
    inst = _make_instrument(db, sess)
    _make_field(db, inst, field_key="rating", data_type="Integer")
    _make_field(db, inst, field_key="comments", data_type="String", order=1)
    db.refresh(inst)

    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=CohortIds(frozenset(), frozenset())
    )
    assert reviewer_row.response_count == 0
    assert reviewee_row.response_count == 0
    assert len(reviewer_row.field_cells) == 2
    assert reviewer_row.field_cells[0].data_type == "Integer"
    assert reviewer_row.field_cells[1].data_type == "String"


def test_reviewer_side_aggregates_responses_by_cohort_reviewers(
    db: Session,
) -> None:
    sess = _make_session(db, code="stats-rev-side")
    inst = _make_instrument(db, sess)
    rating = _make_field(db, inst, field_key="rating", data_type="Integer")
    db.refresh(inst)

    r1 = _make_reviewer(db, sess, name="R1", email="r1@x")
    r2 = _make_reviewer(db, sess, name="R2", email="r2@x")
    r3 = _make_reviewer(db, sess, name="R3", email="r3@x")  # not in cohort
    e1 = _make_reviewee(db, sess, name="E1", email="e1@x")

    # r1, r2 in cohort each rate e1; r3 also rates but isn't in cohort.
    a1 = _make_assignment(db, sess, inst, r1, e1)
    a2 = _make_assignment(db, sess, inst, r2, e1)
    a3 = _make_assignment(db, sess, inst, r3, e1)
    _submit_response(db, a1, rating, "4")
    _submit_response(db, a2, rating, "5")
    _submit_response(db, a3, rating, "1")
    db.commit()

    cohort = CohortIds(
        reviewer_ids=frozenset({r1.id, r2.id}),
        reviewee_ids=frozenset(),
    )
    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    # Reviewer side picks up r1 + r2's ratings (mean 4.5).
    assert reviewer_row.response_count == 2
    assert reviewer_row.field_cells[0].average == 4.5
    # Reviewee side has an empty cohort → empty row.
    assert reviewee_row.response_count == 0


def test_reviewee_side_aggregates_responses_about_cohort_reviewees(
    db: Session,
) -> None:
    sess = _make_session(db, code="stats-ree-side")
    inst = _make_instrument(db, sess)
    rating = _make_field(db, inst, field_key="rating", data_type="Integer")
    db.refresh(inst)

    r1 = _make_reviewer(db, sess, name="R1", email="r1@x")
    e1 = _make_reviewee(db, sess, name="E1", email="e1@x")
    e2 = _make_reviewee(db, sess, name="E2", email="e2@x")
    e3 = _make_reviewee(db, sess, name="E3", email="e3@x")  # not in cohort

    a1 = _make_assignment(db, sess, inst, r1, e1)
    a2 = _make_assignment(db, sess, inst, r1, e2)
    a3 = _make_assignment(db, sess, inst, r1, e3)
    _submit_response(db, a1, rating, "5")
    _submit_response(db, a2, rating, "3")
    _submit_response(db, a3, rating, "1")
    db.commit()

    cohort = CohortIds(
        reviewer_ids=frozenset(),
        reviewee_ids=frozenset({e1.id, e2.id}),
    )
    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    # Reviewee side picks up the two responses about e1 + e2 (mean 4.0).
    assert reviewee_row.response_count == 2
    assert reviewee_row.field_cells[0].average == 4.0
    assert reviewer_row.response_count == 0


def test_only_submitted_responses_count(db: Session) -> None:
    """A draft response (``submitted_at IS NULL``) on a different
    assignment is excluded from the aggregate even when its
    reviewer is in the cohort."""
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
    _submit_response(db, a2, rating, "9", submitted=False)  # draft
    db.commit()

    cohort = CohortIds(
        reviewer_ids=frozenset({r1.id}),
        reviewee_ids=frozenset(),
    )
    reviewer_row, _ = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    # The draft "9" on a2 is excluded; only the submitted "4"
    # on a1 feeds the average.
    assert reviewer_row.response_count == 1
    assert reviewer_row.field_cells[0].average == 4.0


def test_only_in_session_assignments_aggregated(db: Session) -> None:
    sess_a = _make_session(db, code="stats-cross-sess-a")
    sess_b = _make_session(db, code="stats-cross-sess-b")
    inst_a = _make_instrument(db, sess_a)
    rating_a = _make_field(
        db, inst_a, field_key="rating", data_type="Integer"
    )
    inst_b = _make_instrument(db, sess_b)
    rating_b = _make_field(
        db, inst_b, field_key="rating", data_type="Integer"
    )
    db.refresh(inst_a)
    db.refresh(inst_b)

    r_a = _make_reviewer(db, sess_a, name="R", email="r@a")
    e_a = _make_reviewee(db, sess_a, name="E", email="e@a")
    r_b = _make_reviewer(db, sess_b, name="R", email="r@b")
    e_b = _make_reviewee(db, sess_b, name="E", email="e@b")
    a_a = _make_assignment(db, sess_a, inst_a, r_a, e_a)
    a_b = _make_assignment(db, sess_b, inst_b, r_b, e_b)
    _submit_response(db, a_a, rating_a, "4")
    _submit_response(db, a_b, rating_b, "9")  # other session
    db.commit()

    cohort = CohortIds(
        reviewer_ids=frozenset({r_a.id, r_b.id}),
        reviewee_ids=frozenset({e_a.id, e_b.id}),
    )
    reviewer_row, _ = build_cohort_stats_for_instrument(
        db, instrument=inst_a, cohort=cohort
    )
    # Only inst_a's responses contribute; the cross-session "9"
    # rides under a different instrument id and is skipped.
    assert reviewer_row.response_count == 1
    assert reviewer_row.field_cells[0].average == 4.0


def test_field_cells_in_field_order_match_per_row(db: Session) -> None:
    """Reviewer and reviewee rows must line up column-by-column
    so the template can render them as parallel rows."""
    sess = _make_session(db, code="stats-order")
    inst = _make_instrument(db, sess)
    _make_field(db, inst, field_key="z_last", data_type="String", order=2)
    _make_field(db, inst, field_key="a_first", data_type="Integer", order=0)
    _make_field(db, inst, field_key="m_mid", data_type="String", order=1)
    db.refresh(inst)

    reviewer_row, reviewee_row = build_cohort_stats_for_instrument(
        db,
        instrument=inst,
        cohort=CohortIds(frozenset(), frozenset()),
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
    # Only ``rating`` submitted; ``notes`` left blank.
    _submit_response(db, a1, rating, "5")
    _submit_response(db, a1, notes, "")
    db.commit()

    cohort = CohortIds(
        reviewer_ids=frozenset({r1.id}),
        reviewee_ids=frozenset({e1.id}),
    )
    reviewer_row, _ = build_cohort_stats_for_instrument(
        db, instrument=inst, cohort=cohort
    )
    # rating cell has the value; notes cell is empty.
    assert reviewer_row.field_cells[0].response_count == 1
    assert reviewer_row.field_cells[1].response_count == 0
    # Total responses summed across fields.
    assert reviewer_row.response_count == 1
