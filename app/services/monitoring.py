"""Per-session monitoring queries used by the operator running-session
pages (Manage Invitations, Responses).

The "incomplete" classification mirrors the criterion locked in
``segment_09_3A.md``: a reviewer is incomplete iff they are not in the
``submitted`` pill state, which collapses both "never opened",
"opened-but-not-submitted", and "submitted-with-warn-override that still
has missing required" into a single bucket.

The reviewee-centric ``per_reviewee_coverage`` (Segment 11C Part 1 PR 3)
classifies reviewees into Complete / Adequate / At risk / No responses
buckets based on the fraction of their assigned reviewers who have
submitted. Thresholds live in ``AT_RISK_THRESHOLDS`` — a single
constant operators can later tune via a session-level setting.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Invitation,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service


# At-risk classification thresholds for the Responses page. A reviewee
# whose responding-reviewer fraction is at least ``adequate_fraction``
# (but not 100%) renders as "adequate"; below that (and > 0) is
# "at risk"; 0 is "no responses"; 100% is "complete".
AT_RISK_THRESHOLDS = {
    "adequate_fraction": 0.5,
}


@dataclass
class ReviewerProgress:
    reviewer: Reviewer
    invitation: Invitation | None
    assignment_count: int
    completed_count: int
    missing_required_count: int
    required_total: int
    pill_state: str  # "not started" | "in progress" | "submitted"
    last_reminder_at: object | None  # datetime|None — keep generic for templates

    @property
    def is_incomplete(self) -> bool:
        return self.pill_state != "submitted"

    @property
    def required_done(self) -> int:
        return self.required_total - self.missing_required_count


def _assigned_active_reviewers(db: Session, session_id: int) -> list[Reviewer]:
    rows = db.execute(
        select(Reviewer)
        .join(Assignment, Assignment.reviewer_id == Reviewer.id)
        .where(
            Assignment.session_id == session_id,
            Assignment.include.is_(True),
            Reviewer.status == "active",
        )
        .distinct()
        .order_by(Reviewer.email)
    ).scalars()
    return list(rows)


def _invitations_by_reviewer(
    db: Session, session_id: int
) -> dict[int, Invitation]:
    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session_id)
    ).scalars()
    return {inv.reviewer_id: inv for inv in rows}


def per_reviewer_progress(
    db: Session, review_session: ReviewSession
) -> list[ReviewerProgress]:
    reviewers = _assigned_active_reviewers(db, review_session.id)
    invitations = _invitations_by_reviewer(db, review_session.id)
    # Group keys are computed once for the whole session and passed
    # to each per-reviewer rollup. Computing them inside the loop
    # would re-scan the relationships table once per reviewer.
    all_assignments = list(
        db.execute(
            select(Assignment)
            .options(joinedload(Assignment.reviewee))
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    group_key_by_assignment = responses_service.group_keys(
        db, assignments=all_assignments, session_id=review_session.id
    )
    out: list[ReviewerProgress] = []
    for reviewer in reviewers:
        state = responses_service.reviewer_session_state(
            db,
            reviewer=reviewer,
            session_id=review_session.id,
            group_key_by_assignment=group_key_by_assignment,
        )
        invitation = invitations.get(reviewer.id)
        out.append(
            ReviewerProgress(
                reviewer=reviewer,
                invitation=invitation,
                assignment_count=state.total_assignments,
                completed_count=state.completed_count,
                missing_required_count=state.missing_required_count,
                required_total=state.required_total,
                pill_state=state.pill_state,
                last_reminder_at=invitation.last_reminder_at if invitation else None,
            )
        )
    return out


@dataclass
class SummaryCounts:
    assigned: int
    invited: int
    opened: int
    submitted: int
    incomplete: int


def summary_counts(
    db: Session, review_session: ReviewSession
) -> SummaryCounts:
    rows = per_reviewer_progress(db, review_session)
    invited = sum(
        1 for r in rows if r.invitation is not None and r.invitation.status != "pending"
    )
    opened = sum(
        1 for r in rows if r.invitation is not None and r.invitation.status == "opened"
    )
    submitted = sum(1 for r in rows if r.pill_state == "submitted")
    incomplete = sum(1 for r in rows if r.is_incomplete)
    return SummaryCounts(
        assigned=len(rows),
        invited=invited,
        opened=opened,
        submitted=submitted,
        incomplete=incomplete,
    )


@dataclass
class RevieweeCoverage:
    reviewee: Reviewee
    reviewer_count: int
    completed_count: int
    pill_state: str  # "complete" | "adequate" | "at risk" | "no responses"
    last_response_at: datetime | None

    @property
    def is_at_risk(self) -> bool:
        return self.pill_state in ("at risk", "no responses")


def _classify_coverage(completed: int, total: int) -> str:
    if total == 0 or completed == 0:
        return "no responses"
    if completed == total:
        return "complete"
    fraction = completed / total
    if fraction >= AT_RISK_THRESHOLDS["adequate_fraction"]:
        return "adequate"
    return "at risk"


def _assignment_complete(
    db: Session, assignment: Assignment, fields: list[InstrumentResponseField]
) -> tuple[bool, datetime | None]:
    """Returns ``(is_complete, latest_submitted_at)`` for one assignment.

    "Complete" mirrors the reviewer-side definition: every required
    response field has a non-empty value with a non-null ``submitted_at``.
    The second tuple element is the most recent ``submitted_at`` across
    all response rows on the assignment (or ``None``)."""
    rows = list(
        db.execute(
            select(Response).where(Response.assignment_id == assignment.id)
        ).scalars()
    )
    if not rows:
        return False, None
    required_ids = {f.id for f in fields if f.required}
    by_field = {r.response_field_id: r for r in rows}
    is_complete = True
    if not required_ids:
        is_complete = True  # no required → first response counts as done
    else:
        for fid in required_ids:
            r = by_field.get(fid)
            if r is None or (r.value or "") == "" or r.submitted_at is None:
                is_complete = False
                break
    submitted_times = [r.submitted_at for r in rows if r.submitted_at is not None]
    latest = max(submitted_times) if submitted_times else None
    return is_complete, latest


def per_reviewee_coverage(
    db: Session, review_session: ReviewSession
) -> list[RevieweeCoverage]:
    """Per-reviewee coverage rows for the Responses page.

    Joins ``reviewees ⨯ assignments ⨯ responses ⨯ instruments``;
    classifies each reviewee per ``AT_RISK_THRESHOLDS``."""
    assignments = list(
        db.execute(
            select(Assignment)
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    if not assignments:
        return []

    instrument_ids = {a.instrument_id for a in assignments}
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    if instrument_ids:
        for f in db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id.in_(instrument_ids)
            )
        ).scalars():
            fields_by_instrument.setdefault(f.instrument_id, []).append(f)

    by_reviewee: dict[int, list[Assignment]] = {}
    for a in assignments:
        by_reviewee.setdefault(a.reviewee_id, []).append(a)

    reviewees = list(
        db.execute(
            select(Reviewee)
            .where(Reviewee.id.in_(by_reviewee.keys()))
            .order_by(Reviewee.email_or_identifier)
        ).scalars()
    )

    out: list[RevieweeCoverage] = []
    for reviewee in reviewees:
        rs = by_reviewee.get(reviewee.id, [])
        completed = 0
        latest: datetime | None = None
        for a in rs:
            fields = fields_by_instrument.get(a.instrument_id, [])
            is_complete, last_at = _assignment_complete(db, a, fields)
            if is_complete:
                completed += 1
            if last_at is not None and (latest is None or last_at > latest):
                latest = last_at
        pill = _classify_coverage(completed, len(rs))
        out.append(
            RevieweeCoverage(
                reviewee=reviewee,
                reviewer_count=len(rs),
                completed_count=completed,
                pill_state=pill,
                last_response_at=latest,
            )
        )
    return out


__all__ = [
    "AT_RISK_THRESHOLDS",
    "ReviewerProgress",
    "RevieweeCoverage",
    "SummaryCounts",
    "per_reviewer_progress",
    "per_reviewee_coverage",
    "summary_counts",
]
