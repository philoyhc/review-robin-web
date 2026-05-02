"""Per-session monitoring queries used by the operator monitoring page.

Segment 9.3 only — no per-reviewee progress (that's deferred). The
"incomplete" classification mirrors the criterion locked in
``segment_09_3A.md``: a reviewer is incomplete iff they are not in the
``submitted`` pill state, which collapses both "never opened",
"opened-but-not-submitted", and "submitted-with-warn-override that still
has missing required" into a single bucket.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Invitation,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service


@dataclass
class ReviewerProgress:
    reviewer: Reviewer
    invitation: Invitation | None
    assignment_count: int
    completed_count: int
    missing_required_count: int
    pill_state: str  # "not started" | "in progress" | "submitted"
    last_reminder_at: object | None  # datetime|None — keep generic for templates

    @property
    def is_incomplete(self) -> bool:
        return self.pill_state != "submitted"


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
    out: list[ReviewerProgress] = []
    for reviewer in reviewers:
        state = responses_service.reviewer_session_state(
            db, reviewer=reviewer, session_id=review_session.id
        )
        invitation = invitations.get(reviewer.id)
        out.append(
            ReviewerProgress(
                reviewer=reviewer,
                invitation=invitation,
                assignment_count=state.total_assignments,
                completed_count=state.completed_count,
                missing_required_count=state.missing_required_count,
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


__all__ = [
    "ReviewerProgress",
    "SummaryCounts",
    "per_reviewer_progress",
    "summary_counts",
]
