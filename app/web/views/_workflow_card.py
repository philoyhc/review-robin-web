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
from app.services import scheduled_events
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
    # Wave 4 PR 2 — switched from rule-set-centric ``has_unpinned``
    # to ``has_unconfigured``, which knows that new-model instruments
    # default to Full Matrix (rule_set_id NULL is fine) but require at
    # least one visible response field instead.
    has_unconfigured = instruments_service.has_unconfigured(
        db, review_session.id
    )
    is_draft = lifecycle.is_draft(review_session)
    is_validated = lifecycle.is_validated(review_session)
    is_ready = lifecycle.is_ready(review_session)
    is_expired = lifecycle.is_expired(review_session)

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
        reviewer_count == 0 or reviewee_count == 0 or has_unconfigured
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

    is_archived = lifecycle.is_archived(review_session)
    response_release_window_open = (
        lifecycle.is_response_release_window_open(review_session)
    )
    # Single-row Workflow card (2026-06-03 redesign). Every state
    # surfaces ≤ 4 live buttons; inactive buttons are hidden, not
    # rendered as disabled greys. Each visible button fills 25%
    # of the row's width via the grid layout in base.html. Pruning
    # rules:
    # - Create invites hides once invitations exist (no
    #   regenerate-from-the-card affordance);
    # - Send invites hides once invitations are sent;
    # - Release / Stop share a slot, mutually exclusive on
    #   ``is_response_release_window_open``;
    # - Archive surfaces only once the session is ``expired``.
    invitations_generated = invitations.has_invitations(
        db, review_session.id
    )
    invitations_sent = invitations.has_sent_invitations(
        db, review_session.id
    )
    revert_visible = is_validated or is_ready or is_expired
    prepare_visible = (is_draft and not is_setup_empty) or is_validated
    create_invites_visible = (
        is_validated or is_ready
    ) and not invitations_generated
    send_invites_visible = (
        (is_validated or is_ready)
        and invitations_generated
        and not invitations_sent
    )
    activate_visible = is_validated
    send_reminders_visible = is_ready and invitations_sent
    close_visible = is_ready
    release_responses_visible = (
        (is_ready or is_expired)
        and not is_archived
        and not response_release_window_open
    )
    # Stop release lives on the same post-activation gate as
    # Release — otherwise a backdated ``responses_release_at`` on a
    # draft / validated session would flip the window-open check to
    # True and surface Stop in a pre-activation state, blowing the
    # ≤4-visible-button budget (e.g. validated + no invites would
    # render Revert · Prepare · Create invites · Activate · Stop).
    stop_release_visible = (
        response_release_window_open
        and (is_ready or is_expired)
        and not is_archived
    )
    archive_visible = is_expired
    return {
        "is_draft": is_draft,
        "is_validated": is_validated,
        "is_ready": is_ready,
        "is_expired": is_expired,
        "is_archived": is_archived,
        "revert_visible": revert_visible,
        "prepare_visible": prepare_visible,
        "create_invites_visible": create_invites_visible,
        "send_invites_visible": send_invites_visible,
        "activate_visible": activate_visible,
        "send_reminders_visible": send_reminders_visible,
        "close_visible": close_visible,
        "release_responses_visible": release_responses_visible,
        "stop_release_visible": stop_release_visible,
        "archive_visible": archive_visible,
        "is_setup_empty": is_setup_empty,
        "is_pre_generate": is_pre_generate,
        "invitations_generated": invitations_generated,
        "invitations_sent": invitations_sent,
        "validation_summary": validation_summary,
        "validation_issues_by_severity": validation_issues_by_severity,
        "setup_checklist": {
            "reviewers_ok": reviewer_count > 0,
            "reviewees_ok": reviewee_count > 0,
            "instruments_configured_ok": not has_unconfigured,
        },
        "super_failure": super_failure,
        "prepare_confirm": prepare_confirm_ctx,
        "scheduled_activation_caption": build_scheduled_activation_caption(
            db, review_session
        ),
        "manual_activate_cancellation": build_manual_activate_cancellation(
            review_session
        ),
        "auto_send_invites_caption": build_auto_send_invites_caption(
            db, review_session
        ),
        "auto_send_reminders_caption": build_auto_send_reminders_caption(
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


def build_schedule_timeline(
    review_session: ReviewSession,
    session_timezone: str,
) -> list[dict[str, str]]:
    """Resolve every set anchor + offset on the session into a
    chronologically-sorted list of timeline rows for the Create /
    Edit Schedule timeline preview block (Segment 18G PR 2B).

    Each row is ``{"at": "<localized date/time>", "label": "<event>"}``.
    Returns ``[]`` when neither ``scheduled_activate_at`` nor any
    ``invite_offsets`` entry resolves.

    Rows so far:

    - Auto-send invites (one row per resolved ``invite_offsets`` entry)
    - Session activates (``scheduled_activate_at``)
    - Auto-send reminders (one row per resolved ``reminder_offsets`` entry)
    - Session ends (``deadline``)

    Parts 4 / 5 will extend this list with their own entries
    (auto-archive, retention purge) so the timeline gradually becomes
    the full session-lifecycle visualisation.
    """
    rows: list[tuple[datetime, str]] = []
    anchor = review_session.scheduled_activate_at
    if anchor is not None:
        anchor_aware = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
        rows.append((anchor_aware, "Session activates (Start)"))
        offsets = review_session.invite_offsets or []
        if isinstance(offsets, list):
            for entry in offsets:
                if not isinstance(entry, str):
                    continue
                try:
                    delta = scheduled_events.parse_iso_duration(entry)
                except (ValueError, AttributeError):
                    continue
                rows.append(
                    (
                        anchor_aware + delta,
                        f"Auto-send invites ({entry})",
                    )
                )
    deadline = review_session.deadline
    if deadline is not None:
        deadline_aware = (
            deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        )
        rows.append((deadline_aware, "Session ends (End)"))
        reminder_offsets = review_session.reminder_offsets or []
        if isinstance(reminder_offsets, list):
            for entry in reminder_offsets:
                if not isinstance(entry, str):
                    continue
                try:
                    delta = scheduled_events.parse_iso_duration(entry)
                except (ValueError, AttributeError):
                    continue
                rows.append(
                    (
                        deadline_aware + delta,
                        f"Auto-send reminders ({entry})",
                    )
                )
    rows.sort(key=lambda row: row[0])
    return [
        {
            "at": date_formatting.format_datetime(at, session_timezone),
            "label": label,
        }
        for at, label in rows
    ]


def build_auto_send_invites_caption(
    db: Session,
    review_session: ReviewSession,
) -> dict[str, str] | None:
    """Return the Workflow-card right-column caption for auto-send
    invites, or ``None`` when nothing to show.

    Tones:

    - ``invite_offsets`` unset → ``None`` (nothing configured).
    - ``invite_offsets`` set + ``scheduled_activate_at`` unset →
      amber-grey "inactive: no Start to anchor against" (the
      §8.2.2 anchor-null state).
    - ``invite_offsets`` set + Start set + session not yet
      Prepared (``draft``) → amber warning ("Prepare session
      before then or these will skip"). The trigger
      ``_observe_scheduled_invites`` skips with
      ``reason="not_prepared"`` in this case to match the
      operator-route gate ``_require_validated_or_ready``.
    - ``invite_offsets`` set + Start set + Prepared (``validated``
      or ``ready``) + invitations not yet created → amber
      warning ("create invitations before then or these will
      skip"). The trigger skips with
      ``reason="invitations_not_created"`` in this case.
    - ``invite_offsets`` set + Start set + Prepared + invitations
      created → green calm caption ("System will dispatch
      automatically; you can also Send all now").
    """
    offsets = review_session.invite_offsets or []
    if not isinstance(offsets, list) or not offsets:
        return None

    if review_session.scheduled_activate_at is None:
        # PR 2C: offsets set + Start unset → inactive via anchor-null.
        entry_word = "entry" if len(offsets) == 1 else "entries"
        return {
            "tone": "amber-grey",
            "text": (
                f"Auto-send invites are configured ({len(offsets)} "
                f"{entry_word}) but currently inactive — no Start to "
                f"anchor against. They reactivate when Start is re-set."
            ),
        }

    # Resolve the earliest fire moment for display
    anchor = review_session.scheduled_activate_at
    anchor_aware = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
    fire_moments: list[datetime] = []
    for entry in offsets:
        if not isinstance(entry, str):
            continue
        try:
            delta = scheduled_events.parse_iso_duration(entry)
        except ValueError:
            continue
        fire_moments.append(anchor_aware + delta)
    if not fire_moments:
        return None

    session_tz = sessions_service.resolve_session_timezone(review_session)
    earliest = min(fire_moments)
    earliest_text = date_formatting.format_datetime(earliest, session_tz)

    if lifecycle.is_draft(review_session):
        return {
            "tone": "amber-warning",
            "text": (
                f"Auto-send scheduled at {earliest_text} — currently "
                f"inactive: Prepare session before then or these "
                f"will skip."
            ),
        }
    if not invitations.has_invitations(db, review_session.id):
        return {
            "tone": "amber-warning",
            "text": (
                f"Auto-send scheduled at {earliest_text} — currently "
                f"inactive: create invitations before then or these "
                f"will skip."
            ),
        }
    return {
        "tone": "green",
        "text": (
            f"Auto-send scheduled at {earliest_text}. System will "
            f"dispatch automatically; you can also Send all now."
        ),
    }


def build_auto_send_reminders_caption(
    db: Session,
    review_session: ReviewSession,
) -> dict[str, str] | None:
    """Return the Workflow-card right-column caption for auto-send
    reminders, or ``None`` when nothing to show.

    Mirrors :func:`build_auto_send_invites_caption`. Tones:

    - ``reminder_offsets`` unset → ``None`` (nothing configured).
    - ``reminder_offsets`` set + ``deadline`` unset → amber-grey
      "inactive: no End to anchor against" caption (§8.2.2
      anchor-null state).
    - ``reminder_offsets`` set + End set + session not ``ready`` →
      amber warning ("activate the session before then or these
      will skip").
    - ``reminder_offsets`` set + End set + session ``ready`` +
      no invitations created → amber warning ("create
      invitations before then or these will skip"). The trigger
      `_observe_scheduled_reminders` skips with
      ``reason="no_invitations"`` in this case, since reminders
      piggyback on existing ``Invitation`` rows.
    - ``reminder_offsets`` set + End set + session ``ready`` +
      invitations exist → green calm caption ("System will
      dispatch automatically; you can also Send reminders to
      incomplete now").
    """
    offsets = review_session.reminder_offsets or []
    if not isinstance(offsets, list) or not offsets:
        return None

    if review_session.deadline is None:
        entry_word = "entry" if len(offsets) == 1 else "entries"
        return {
            "tone": "amber-grey",
            "text": (
                f"Auto-send reminders are configured ({len(offsets)} "
                f"{entry_word}) but currently inactive — no End to "
                f"anchor against. They reactivate when End is re-set."
            ),
        }

    anchor = review_session.deadline
    anchor_aware = anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc)
    fire_moments: list[datetime] = []
    for entry in offsets:
        if not isinstance(entry, str):
            continue
        try:
            delta = scheduled_events.parse_iso_duration(entry)
        except ValueError:
            continue
        fire_moments.append(anchor_aware + delta)
    if not fire_moments:
        return None

    session_tz = sessions_service.resolve_session_timezone(review_session)
    earliest = min(fire_moments)
    earliest_text = date_formatting.format_datetime(earliest, session_tz)

    if review_session.status != lifecycle.SessionStatus.ready.value:
        return {
            "tone": "amber-warning",
            "text": (
                f"Auto-send reminders scheduled at {earliest_text} — "
                f"currently inactive: activate the session before then "
                f"or these will skip."
            ),
        }
    # Reminders piggyback on existing Invitation rows (each reminder
    # reuses the previously-issued invitation URL). With no
    # invitations created, _observe_scheduled_reminders skips with
    # reason="no_invitations" — surface that as amber here so the
    # caption matches the trigger's behaviour.
    if not invitations.has_invitations(db, review_session.id):
        return {
            "tone": "amber-warning",
            "text": (
                f"Auto-send reminders scheduled at {earliest_text} — "
                f"currently inactive: create invitations before then "
                f"or these will skip."
            ),
        }
    return {
        "tone": "green",
        "text": (
            f"Auto-send reminders scheduled at {earliest_text}. System "
            f"will dispatch automatically; you can also Send reminders "
            f"to incomplete now."
        ),
    }


def build_manual_activate_cancellation(
    review_session: ReviewSession,
) -> dict[str, object] | None:
    """Return the manual-activate confirmation message + count for
    the Workflow card's Activate button (Segment 18G PR 2C), or
    ``None`` when no auto-sends would be cancelled.

    Manual Activate (operator clicks Activate before the scheduled
    fire) clears ``scheduled_activate_at`` as a side effect (per
    PR 1B). With Start cleared, ``invite_offsets`` becomes inert
    via the §8.2.2 anchor-null rule — any remaining auto-sends
    that haven't fired yet are effectively cancelled. The Activate
    button surfaces a confirmation modal so the operator can
    acknowledge that trade-off before committing.

    Returns ``None`` when:

    - ``invite_offsets`` is empty / unset, or
    - ``scheduled_activate_at`` is already unset (nothing to
      cancel; no auto-sends would have fired anyway), or
    - the session isn't in a state where Activate would be
      offered (``validated``).

    Note: the count reported is the **total** ``invite_offsets``
    list length, not the future-only subset. The lazy observer has
    already fired any past-due entries by the time the Workflow
    card renders, so a conservative "N entries scheduled" message
    is accurate enough for an operator-facing confirmation. The
    audit log carries the precise per-entry fired/skipped record.
    """
    if not lifecycle.is_validated(review_session):
        return None
    if review_session.scheduled_activate_at is None:
        return None
    offsets = review_session.invite_offsets or []
    if not isinstance(offsets, list) or not offsets:
        return None
    count = len(offsets)
    plural = "" if count == 1 else "s"
    return {
        "pending_count": count,
        "message": (
            f"{count} scheduled auto-send invitation{plural} will be "
            f"cancelled by activating now. Continue with manual "
            f"activation?"
        ),
    }
