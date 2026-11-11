"""The handoff status a sender reads (segment 23C; `spec/handoffs.md` §10).

A view adapter, not a service: it composes what Review Robin's own pages
read (`session_status_pills`, the Validate run, Monitoring's tables) into
one JSON-ready projection, and `session_status_pills` lives here in
`app/web/views/`, which services may not import. Reads only: no
lifecycle step, no validation stamp, no audit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Instrument, Reviewer, ReviewSession
from app.services import instruments as instruments_service
from app.services import monitoring
from app.services.lifecycle_display import lifecycle_display_label
from app.services.validation import validate_session_setup
from app.web.views._setup import session_status_pills
from app.web.views._workflow_card import build_workflow_card_context

#: The Workflow card's buttons, in its order, by the context key that
#: says whether each shows now.
_ACTIONS = (
    ("revert", "revert_visible"),
    ("prepare", "prepare_visible"),
    ("send_invites", "send_invites_visible"),
    ("activate", "activate_visible"),
    ("send_reminders", "send_reminders_visible"),
    ("close", "close_visible"),
    ("release_responses", "release_responses_visible"),
    ("stop_release", "stop_release_visible"),
    ("archive", "archive_visible"),
)

#: The projection's shape. 3 (segment 23C): Review Robin's own readings.
STATUS_SCHEMA_VERSION = 3
#: Why ``progress.provisional`` is true: Review Robin validates no session
#: with an instrument not set up, so until then the assignments are an
#: untouched rule's stand-in rather than the review's.
PROVISIONAL_REASON = "instruments_not_set_up"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:  # SQLite drops tzinfo on write; naive is UTC
        value = value.replace(tzinfo=UTC)
    return value.isoformat(timespec="seconds")


def _instruments(db: Session, review_session: ReviewSession) -> list[dict[str, object]]:
    counts = {
        instrument_id: count
        for instrument_id, count in db.execute(
            select(Assignment.instrument_id, func.count(Assignment.id))
            .where(Assignment.session_id == review_session.id, Assignment.include.is_(True))
            .group_by(Assignment.instrument_id)
        )
    }
    rows: list[dict[str, object]] = []
    for instrument in db.scalars(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.session_seq)
    ):
        rows.append(
            {
                "seq": instrument.session_seq,
                "name": instrument.name,
                "short_label": instrument.short_label or "",
                "set_up": instruments_service.is_configured(db, instrument),
                "scope": "per_reviewee" if instrument.group_kind is None else "group",
                "assignments": counts.get(instrument.id, 0),
            }
        )
    return rows


def handoff_status(db: Session, review_session: ReviewSession) -> dict[str, object]:
    """Review Robin's readings of the session, each section as its pages
    show it. ``session_home_url`` is the route's to add."""
    pills = session_status_pills(db, review_session)
    instruments = _instruments(db, review_session)
    issues = validate_session_setup(db, review_session)
    rows = monitoring.per_reviewer_progress(db, review_session)
    summary = monitoring.summarize(rows)
    coverage = monitoring.per_reviewee_coverage(db, review_session)
    provisional = pills.instrument_count == 0 or (
        pills.instruments_configured < pills.instrument_count
    )
    errors = sum(1 for issue in issues if issue.severity.value == "error")
    card = build_workflow_card_context(db, review_session, return_to="handoff", issues=issues)
    checklist = card["setup_checklist"]
    return {
        "status_schema_version": STATUS_SCHEMA_VERSION,
        "session_ref": review_session.public_id,
        "session_code": review_session.code,
        "name": review_session.name,
        "state": review_session.status,
        "state_label": lifecycle_display_label(review_session.status),
        "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        # The status row every session page shows (`session_status_pills`).
        "status_row": {
            "reviewers": pills.reviewer_count,
            "reviewees": pills.reviewee_count,
            "relationships": pills.relationship_count,
            "observers": pills.observer_count,
            "assignments": pills.assignment_count,
            "instruments": pills.instrument_count,
            "instruments_set_up": pills.instruments_configured,
            "invitations": pills.invitations_state,
            "responses_drafts": pills.responses_drafts,
            "responses_submitted": pills.responses_submitted,
        },
        "schedule": {
            "display_timezone": review_session.display_timezone,
            "scheduled_activate_at": _iso(review_session.scheduled_activate_at),
            "activated_at": _iso(review_session.activated_at),
            "deadline": _iso(review_session.deadline),
            "responses_release_at": _iso(review_session.responses_release_at),
            "responses_release_until": _iso(review_session.responses_release_until),
        },
        # The Workflow card's own reading. A session whose setup is not
        # complete (no reviewers, no reviewees, or an instrument not set
        # up) offers no Prepare: that, not the Validate rules, is what
        # keeps it from validating.
        "workflow": {
            "setup_complete": not card["is_setup_empty"],
            "checklist": {
                "reviewers": checklist["reviewers_ok"],
                "reviewees": checklist["reviewees_ok"],
                "instruments_set_up": checklist["instruments_configured_ok"],
            },
            "actions": [name for name, key in _ACTIONS if card[key]],
            "invitations_generated": card["invitations_generated"],
            "invitations_sent": card["invitations_sent"],
            "due": [line["text"] for line in card["due_lines"]],
        },
        # The Validate page's rules, read only (no stamp).
        "validation": {
            "errors": errors,
            "warnings": sum(1 for issue in issues if issue.severity.value == "warning"),
            "issues": [
                {
                    "rule": issue.rule_key or "",
                    "severity": issue.severity.value,
                    "message": issue.message,
                    "page": issue.fix_page_label or "",
                }
                for issue in issues
            ],
        },
        "instruments": instruments,
        # Monitoring's readings. Always reported; provisional, with its
        # reason, while any instrument is not set up (author, 2026-11-11).
        "progress": {
            "provisional": provisional,
            "provisional_reason": PROVISIONAL_REASON if provisional else None,
            "assignments": sum(p.assignment_count for p in rows),
            "assignments_completed": sum(p.completed_count for p in rows),
            "reviewers_assigned": summary.assigned,
            "reviewers_invited": summary.invited,
            "reviewers_opened": summary.opened,
            "reviewers_submitted": summary.submitted,
            "reviewers_incomplete": summary.incomplete,
        },
        "reviewers": [_reviewer_row(p) for p in rows],
        "reviewees": [
            {
                "key": c.reviewee.email_or_identifier,
                "name": c.reviewee.name,
                "state": c.pill_state,
                "reviewers": c.reviewer_count,
                "completed": c.completed_count,
                "last_response_at": _iso(c.last_response_at),
            }
            for c in coverage
        ],
    }


def _reviewer_row(progress: monitoring.ReviewerProgress) -> dict[str, object]:
    reviewer: Reviewer = progress.reviewer
    return {
        "email": reviewer.email,
        "name": reviewer.name,
        "state": progress.pill_state,
        "assignments": progress.assignment_count,
        "completed": progress.completed_count,
        "missing_required": progress.missing_required_count,
        "invitation": progress.invitation.status if progress.invitation else None,
        "last_reminder_at": _iso(progress.last_reminder_at),
    }
