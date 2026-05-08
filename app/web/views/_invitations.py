"""Manage Invitations page row builder — Segment 11C Part 1's
consolidated reviewer-centric view at
``/operator/sessions/{id}/invitations``.

Slice 3 of the §12.B ladder (``guide/major_refactor.md``).

Owns the ``InvitationsRow`` dataclass and ``build_invitations_rows``
adapter that joins per-reviewer progress (from
``monitoring.per_reviewer_progress``) with the latest invitation
outbox row's status + sent_at — in a single batched outbox query
rather than firing N queries per row.

Filter / search helpers (`filter_invitations_rows`,
`invitations_search_options`) and the related
`INVITATIONS_STATUS_OPTIONS` constant live in ``_filters.py``
(PR 4) — they're shared between Invitations and Responses.

Source range in pre-PR-3 ``_legacy.py``: lines 1272-1389.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EmailOutbox, Invitation, Reviewer, ReviewSession
from app.services import invitations as invitations_service
from app.services import monitoring


@dataclass(frozen=True)
class InvitationsRow:
    reviewer: Reviewer
    invitation: Invitation | None
    email_status: str
    """The latest invitation outbox row's status, or ``"not sent"`` when
    no outbox row exists for this reviewer's invitation. Today the value
    set is ``{"not sent", "queued", "sent"}``; Segment 11C Part 2 widens
    it to include ``"sending"`` and ``"failed"``."""
    email_sent_at: datetime | None
    review_progress_state: str
    """``"not started"`` / ``"in progress"`` / ``"submitted"`` —
    pill_state from ``monitoring.ReviewerProgress``."""
    review_progress_done: int
    review_progress_total: int
    required_fields_done: int
    required_fields_total: int
    last_reminder_at: datetime | None

    @property
    def is_incomplete(self) -> bool:
        return self.review_progress_state != "submitted"

    @property
    def summary_state(self) -> str:
        """Single derived state for the Manage Invitations status filter.

        Collapses the otherwise-orthogonal Email Status + Review
        Progress columns into one bucket the operator filters on.
        Mirrors `spec/operations_renew.md` "Status filter values"
        (Manage Invitations) modulo the deferred "stale" bucket.
        """
        if self.email_status == "not sent":
            return "not_sent"
        if self.review_progress_state == "submitted":
            return "submitted"
        if self.review_progress_state == "in progress":
            return "in_progress"
        return "not_started"


def _latest_invitation_outbox_by_reviewer(
    db: Session, session_id: int
) -> dict[int, EmailOutbox]:
    """One latest ``kind="invitation"`` outbox row per reviewer.

    Used by ``build_invitations_rows`` to populate the Email Status +
    Email Sent columns. Sorted descending by created_at then id, then
    the first row per reviewer wins.
    """
    rows = list(
        db.execute(
            select(EmailOutbox)
            .where(
                EmailOutbox.session_id == session_id,
                EmailOutbox.kind == invitations_service.INVITATION_KIND,
                EmailOutbox.reviewer_id.is_not(None),
            )
            .order_by(
                EmailOutbox.created_at.desc(), EmailOutbox.id.desc()
            )
        ).scalars()
    )
    out: dict[int, EmailOutbox] = {}
    for row in rows:
        rid = row.reviewer_id
        if rid is not None and rid not in out:
            out[rid] = row
    return out


def build_invitations_rows(
    db: Session, review_session: ReviewSession
) -> list[InvitationsRow]:
    progress_rows = monitoring.per_reviewer_progress(db, review_session)
    latest_outbox = _latest_invitation_outbox_by_reviewer(db, review_session.id)
    out: list[InvitationsRow] = []
    for p in progress_rows:
        outbox_row = latest_outbox.get(p.reviewer.id)
        if outbox_row is None:
            email_status = "not sent"
            email_sent_at: datetime | None = None
        else:
            email_status = outbox_row.status
            email_sent_at = outbox_row.sent_at
        out.append(
            InvitationsRow(
                reviewer=p.reviewer,
                invitation=p.invitation,
                email_status=email_status,
                email_sent_at=email_sent_at,
                review_progress_state=p.pill_state,
                review_progress_done=p.completed_count,
                review_progress_total=p.assignment_count,
                required_fields_done=p.required_done,
                required_fields_total=p.required_total,
                last_reminder_at=p.last_reminder_at,
            )
        )
    return out
