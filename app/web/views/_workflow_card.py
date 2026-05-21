"""Workflow card context builder — shared by every Operations-row
page that renders ``operator/partials/next_action_card.html``.

After PR 5 of ``spec/workflow_card.md`` A.8, every Operations-row
page route (Assignments today; Validate / Previews / Invitations /
Responses incoming in PRs 6+) builds its template context by
calling ``build_workflow_card_context(...)`` and merging the
returned dict into its page-specific context. The card partial
expects every key in the returned dict to be present.

The builder owns:

- the lifecycle convenience booleans
  (``is_draft`` / ``is_validated`` / ``is_ready``);
- the workflow-card state predicates
  (``is_setup_empty`` / ``is_pre_generate``);
- the readiness summary + per-issue breakdown
  (``validation_summary`` / ``validation_issues_by_severity``);
- the invitation lifecycle flags
  (``invitations_generated`` / ``invitations_sent``);
- the setup-completion checklist for State 1
  (``setup_checklist``);
- the super-button failure banner state (``super_failure``);
- the ``return_to`` slug each Operations-row page uses to land
  the workflow card's POSTs back on itself
  (``next_action_return_to``).

The builder is read-only with one exception: when
``validated_just_ran`` is True (the page's ``?validated=1`` entry
path) AND the readiness report is clean AND the session is still
in draft, it calls ``lifecycle.mark_validated`` to flip
``draft → validated`` before computing the rest of the context.
This matches the historical behaviour of the inline computation in
``_assignments.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.services import (
    assignments,
    csv_imports,
    date_formatting,
    invitations,
    sessions as sessions_service,
    validation,
)
from app.services import instruments as instruments_service
from app.services import session_lifecycle as lifecycle


def build_workflow_card_context(
    db: Session,
    review_session: ReviewSession,
    *,
    return_to: str,
    validated_just_ran: bool = False,
    super_failure: dict[str, str] | None = None,
    prepare_confirm: str | None = None,
    user: User | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build the dict of context keys consumed by the Workflow card.

    ``return_to`` is the operations-row slug for the calling page
    (e.g. ``"assignments"`` / ``"validate"`` / ``"previews"`` /
    ``"invitations"`` / ``"responses"``). It flows into the partial
    as ``next_action_return_to`` and drives the hidden ``return_to``
    field on every workflow-card form so the post-action redirect
    lands back on the same page.

    ``validated_just_ran`` (the page's ``?validated=1`` entry path)
    triggers an inline ``validate_session_setup`` run; when the
    report is clean and the session is still draft, the helper
    flips it to ``validated`` via ``lifecycle.mark_validated``
    before populating the rest of the context. ``user`` and
    ``correlation_id`` are required when this path fires.

    ``prepare_confirm`` (the page's ``?prepare_confirm=responses``
    entry path, 18F) is the Prepare-button's saved-response detour:
    when set to ``"responses"``, the builder dry-runs the reconcile
    via ``assignments.reconcile_impact`` and — if a run would delete
    one or more responses — returns a ``prepare_confirm`` dict
    carrying ``responses_deleted`` / ``deleted_pairs`` so the card
    renders its confirmation block.
    """
    reviewer_count = csv_imports.existing_reviewer_count(
        db, review_session.id
    )
    reviewee_count = csv_imports.existing_reviewee_count(
        db, review_session.id
    )
    has_unpinned = instruments_service.has_unpinned(db, review_session.id)
    is_draft = lifecycle.is_draft(review_session)
    is_validated = lifecycle.is_validated(review_session)
    is_ready = lifecycle.is_ready(review_session)

    validation_summary: dict[str, object] | None = None
    validation_issues_by_severity: dict[str, list] = {
        "errors": [],
        "warnings": [],
        "info": [],
    }
    if validated_just_ran or is_validated:
        issues = validation.validate_session_setup(db, review_session)
        report = lifecycle.build_readiness_report(issues)
        if (
            validated_just_ran
            and report.can_activate
            and is_draft
            and user is not None
        ):
            lifecycle.mark_validated(
                db,
                review_session=review_session,
                user=user,
                report=report,
                correlation_id=correlation_id,
            )
            # Refresh the lifecycle booleans after the flip.
            is_draft = lifecycle.is_draft(review_session)
            is_validated = lifecycle.is_validated(review_session)
        validation_summary = {
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
            "can_activate": report.can_activate and is_validated,
            "needs_acknowledge": report.has_non_blocking_findings,
        }
        validation_issues_by_severity = {
            "errors": report.errors,
            "warnings": report.warnings,
            "info": report.info,
        }

    is_setup_empty = is_draft and (
        reviewer_count == 0 or reviewee_count == 0 or has_unpinned
    )
    is_pre_generate = (
        is_draft
        and not is_setup_empty
        and (
            assignments.existing_count(db, review_session.id) == 0
            or lifecycle.needs_regeneration_after_revert(
                db, review_session.id
            )
        )
    )

    prepare_confirm_ctx: dict[str, int] | None = None
    if prepare_confirm == "responses" and lifecycle.session_has_responses(
        db, review_session
    ):
        impact = assignments.reconcile_impact(db, review_session)
        if impact.responses_deleted > 0:
            prepare_confirm_ctx = {
                "responses_deleted": impact.responses_deleted,
                "deleted_pairs": impact.deleted,
            }

    return {
        "is_draft": is_draft,
        "is_validated": is_validated,
        "is_ready": is_ready,
        "is_setup_empty": is_setup_empty,
        "is_pre_generate": is_pre_generate,
        "invitations_generated": invitations.has_invitations(
            db, review_session.id
        ),
        "invitations_sent": invitations.has_sent_invitations(
            db, review_session.id
        ),
        "validation_summary": validation_summary,
        "validation_issues_by_severity": validation_issues_by_severity,
        "setup_checklist": {
            "reviewers_ok": reviewer_count > 0,
            "reviewees_ok": reviewee_count > 0,
            "instruments_pinned_ok": not has_unpinned,
        },
        "super_failure": super_failure,
        "prepare_confirm": prepare_confirm_ctx,
        "scheduled_activation_caption": build_scheduled_activation_caption(
            db, review_session
        ),
        "next_action_return_to": return_to,
    }


def build_scheduled_activation_caption(
    db: Session,
    review_session: ReviewSession,
) -> dict[str, str] | None:
    """Return the Workflow card right-column caption for the scheduled
    activation (Segment 18G Part 1), or ``None`` when there's nothing
    to show.

    Per the Part 1 plan section in
    ``guide/segment_18G_scheduled_events.md`` (and the matching table
    in ``spec/workflow_card.md``):

    +-----------+------------------------+-----------------------------+
    | Status    | scheduled_activate_at  | Caption                     |
    +===========+========================+=============================+
    | draft     | unset                  | (none)                      |
    | draft     | future                 | amber-warning               |
    | draft     | past (last audit       | amber-grey skipped notice   |
    |           |   was skip / failed)   |                             |
    | validated | unset                  | (none)                      |
    | validated | future                 | green calm                  |
    | ready     | (any — moot)           | (none — handled by status)  |
    +-----------+------------------------+-----------------------------+

    The "skipped" branch is read from the audit log: when there's a
    recent ``session.scheduled_activation_skipped`` or
    ``session.scheduled_activation_failed_persistent`` event AND no
    operator-initiated audit has occurred since, we surface the
    skip caption (one-shot per the Part 1 contract).
    """
    if lifecycle.is_ready(review_session):
        return None

    session_tz = sessions_service.resolve_session_timezone(review_session)

    if review_session.scheduled_activate_at is not None:
        when_text = date_formatting.format_datetime(
            review_session.scheduled_activate_at, session_tz
        )
        if lifecycle.is_validated(review_session):
            return {
                "tone": "green",
                "text": (
                    f"System will auto-activate at {when_text}. "
                    f"You can also click Activate now."
                ),
            }
        # draft + scheduled in future → amber warning. (A past schedule
        # without a skip audit is unusual — could be just-now-due; the
        # caption still tells the operator to Prepare before the
        # observer fires.)
        return {
            "tone": "amber-warning",
            "text": (
                f"Scheduled activation at {when_text} — currently "
                f"inactive: Prepare session before then or the schedule "
                f"will skip."
            ),
        }

    # No schedule set. Surface a skipped / failed notice if the most
    # recent audit row for this session is a 18G Part 1 skip/fail.
    latest = db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == review_session.id)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return None
    skip_types = {
        "session.scheduled_activation_skipped",
        "session.scheduled_activation_failed_persistent",
    }
    if latest.event_type not in skip_types:
        return None
    detail = latest.detail or {}
    context = detail.get("context", {}) if isinstance(detail, dict) else {}
    scheduled_at_iso = (
        context.get("scheduled_at") if isinstance(context, dict) else None
    )
    when_text = "unknown"
    if scheduled_at_iso:
        try:
            parsed = datetime.fromisoformat(scheduled_at_iso)
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            when_text = date_formatting.format_datetime(parsed, session_tz)
    reason = (
        detail.get("reason", "unknown") if isinstance(detail, dict) else "unknown"
    )
    headline = (
        "Scheduled activation"
        if latest.event_type.endswith("skipped")
        else "Scheduled activation gave up"
    )
    return {
        "tone": "amber-grey",
        "text": (
            f"{headline} at {when_text} — reason: {reason}."
        ),
    }




def parse_super_failure(
    super_status: str | None,
    super_step: str | None,
    super_error: str | None,
    super_button: str | None = None,
) -> dict[str, str] | None:
    """Convert a workflow button's redirect failure params into the
    ``super_failure`` dict the partial expects (or ``None`` when
    the URL doesn't carry a failure signal). ``super_button`` is
    ``"prepare"`` or ``"activate"`` per 18F Part 1; when absent (a
    legacy URL), it falls back to ``"prepare"`` for ``generate`` /
    ``validate`` steps and ``"activate"`` for ``activate``."""
    if super_status != "failed":
        return None
    step = super_step or "unknown"
    button = super_button
    if not button:
        if step in {"generate", "validate"}:
            button = "prepare"
        elif step == "activate":
            button = "activate"
        else:
            button = "prepare"
    return {
        "button": button,
        "step": step,
        "error": super_error or "",
    }


__all__ = [
    "build_workflow_card_context",
    "parse_super_failure",
]
