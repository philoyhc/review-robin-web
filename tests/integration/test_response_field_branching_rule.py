"""19T Item 10 rung 3 — the save rule: a closed branch holds no value.

Every writer of ``Response`` rows ends in it: save and submit, the group
re-fan, and the responses import. Each test gives an instrument a branch
directly (no page authors one yet): an Integer parent with the condition
``ge 4``, governing a String field."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    InstrumentResponseField,
    Response,
)
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.responses_import import (
    load_responses,
    parse_responses_csv,
)
from app.services.responses._group_reconciliation import _refan_group_responses

from .test_responses_import import (
    _assignment,
    _build,
    _csv_bytes,
    _response,
    _reviewee,
    _reviewer,
)
from .test_responses_service import _seed


def _branch_default_instrument(db: Session, assignment: Assignment) -> None:
    """Rating (Integer 1–5) governs Comments on the default instrument."""
    fields = {
        f.field_key: f
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == assignment.instrument_id
            )
        ).scalars()
    }
    fields["rating"].branch_op, fields["rating"].branch_value = "ge", "4"
    fields["comments"].branch_parent_id = fields["rating"].id
    db.flush()


def _answers(db: Session, assignment_id: int) -> dict[str, str | None]:
    return {
        field_key: value
        for field_key, value in db.execute(
            select(InstrumentResponseField.field_key, Response.value)
            .join(Response, Response.response_field_id == InstrumentResponseField.id)
            .where(Response.assignment_id == assignment_id)
        ).all()
    }


def _save(db, op, reviewer, review_session, assignment, **values):
    return responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key=k, value=v)
            for k, v in values.items()
        ],
        correlation_id="corr",
    )


def test_an_open_branch_keeps_its_answer(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    _branch_default_instrument(db, assignment)
    _save(db, op, reviewer, review_session, assignment, rating="5", comments="Why")
    assert _answers(db, assignment.id) == {"rating": "5", "comments": "Why"}


def test_a_parent_changed_to_close_its_branch_deletes_the_answer(
    db: Session,
) -> None:
    """Judged on the answers as the save leaves them, so the parent's new
    value decides; the save's audit event counts what went."""
    op, reviewer, review_session, assignment = _seed(db)
    _branch_default_instrument(db, assignment)
    _save(db, op, reviewer, review_session, assignment, rating="5", comments="Why")
    _save(db, op, reviewer, review_session, assignment, rating="2")
    assert _answers(db, assignment.id) == {"rating": "2"}
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["counts"]["branch_answers_removed"] == 1


def test_an_answer_to_a_closed_branch_is_not_stored(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    _branch_default_instrument(db, assignment)
    # Closed by the parent's value in the same save…
    _save(db, op, reviewer, review_session, assignment, rating="2", comments="x")
    assert _answers(db, assignment.id) == {"rating": "2"}
    # …and by an unanswered parent.
    _save(db, op, reviewer, review_session, assignment, rating="", comments="x")
    assert _answers(db, assignment.id) == {}


def test_submit_drops_a_closed_branch_before_stamping(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    _branch_default_instrument(db, assignment)
    _save(db, op, reviewer, review_session, assignment, rating="5", comments="Why")
    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="3")
        ],
        correlation_id="corr",
    )
    assert result.submitted is True
    assert result.submitted_count == 1
    assert _answers(db, assignment.id) == {"rating": "3"}


def test_a_blocked_submit_audits_the_answer_it_removed(db: Session) -> None:
    """A submit blocked on a missing required field still commits its
    drafts, among them a closed branch's deletion, which is audited as the
    draft save it amounts to (Codex on #2640). Clearing the required parent
    both blocks the submit and closes the branch."""
    op, reviewer, review_session, assignment = _seed(db)
    _branch_default_instrument(db, assignment)
    _save(db, op, reviewer, review_session, assignment, rating="5", comments="Why")
    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[
            ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="")
        ],
        correlation_id="corr",
    )
    assert result.submitted is False and result.missing
    assert _answers(db, assignment.id) == {}
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "responses.saved")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["counts"]["branch_answers_removed"] == 1
    assert "submit blocked" in event.summary


def test_no_branch_changes_nothing(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    _save(db, op, reviewer, review_session, assignment, rating="2", comments="x")
    assert _answers(db, assignment.id) == {"rating": "2", "comments": "x"}
    assert responses_service.drop_closed_branch_answers(db, {assignment.id}) == 0


def _governed_q2(db: Session, instrument, q1, *, branched: bool):
    if branched:
        q1.branch_op, q1.branch_value = "ge", "4"
    q2 = InstrumentResponseField(
        instrument_id=instrument.id, field_key="q2", label="Q2", order=2,
        visible=True, _inline_data_type="String",
        branch_parent_id=q1.id if branched else None,
    )
    db.add(q2)
    db.flush()
    return q2


def test_the_import_drops_and_reports_a_closed_branch_answer(db: Session) -> None:
    """The source had no branch; the target does. The answer its parent's
    imported value closes is dropped and reported, not inserted."""
    src, s_inst, s_q1 = _build(db, "br-src")
    s_q2 = _governed_q2(db, s_inst, s_q1, branched=False)
    rvr = _reviewer(db, src, "r@e.edu")
    low = _assignment(db, src, rvr, _reviewee(db, src, "a@e.edu", "A"), s_inst)
    high = _assignment(db, src, rvr, _reviewee(db, src, "b@e.edu", "B"), s_inst)
    _response(db, low, s_q1, "2")
    _response(db, low, s_q2, "stale")
    _response(db, high, s_q1, "5")
    _response(db, high, s_q2, "kept")

    dst, d_inst, d_q1 = _build(db, "br-dst")
    _governed_q2(db, d_inst, d_q1, branched=True)
    d_rvr = _reviewer(db, dst, "r@e.edu")
    d_low = _assignment(db, dst, d_rvr, _reviewee(db, dst, "a@e.edu", "A"), d_inst)
    d_high = _assignment(db, dst, d_rvr, _reviewee(db, dst, "b@e.edu", "B"), d_inst)

    parsed = parse_responses_csv(_csv_bytes(list(serialize_responses(db, src))))
    result = load_responses(db, review_session=dst, rows=parsed)
    assert result.responses == 3
    assert [d.reason for d in result.dropped] == [
        "its branch is closed by the parent field's answer"
    ]
    assert _answers(db, d_low.id) == {"q1": "2"}
    assert _answers(db, d_high.id) == {"q1": "5", "q2": "kept"}


def test_the_group_refan_holds_to_the_rule(db: Session) -> None:
    """The re-fan copies a sibling's answers onto a relocated member; a
    governed answer its branch no longer admits is not carried across."""
    rs, inst, q1 = _build(db, "br-refan", group=True)
    q2 = _governed_q2(db, inst, q1, branched=True)
    rvr = _reviewer(db, rs, "r@e.edu")
    carol = _assignment(
        db, rs, rvr, _reviewee(db, rs, "carol@e.edu", "Carol", tag_1="Team A"), inst
    )
    eve = _assignment(
        db, rs, rvr, _reviewee(db, rs, "eve@e.edu", "Eve", tag_1="Team A"), inst
    )
    # Carol's row predates the rule: a governed answer under a closed branch.
    _response(db, carol, q1, "2")
    _response(db, carol, q2, "stale")
    written = _refan_group_responses(db, session_id=rs.id, assignment_ids={eve.id})
    assert written == 2
    assert _answers(db, eve.id) == {"q1": "2"}

