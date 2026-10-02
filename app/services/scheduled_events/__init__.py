"""Lazy observer for scheduled session-lifecycle events (Segment 18G).

Per ``spec/lifecycle.md`` §8.2 + §8.3: scheduled events fire on
the operator's GET of Session Home (the observer's only caller). Each trigger checks its
precondition (§8.2.3), uses ``SELECT … FOR UPDATE`` on the
session row, and is idempotent via the column clear at the end
of a successful fire.

Originally a single ~1,380-line module; carved into per-concern
submodules in Segment 18O Track A. The public surface is preserved
here as an explicit re-export wall so external callers — both
``from app.services import scheduled_events`` and
``from app.services.scheduled_events import <symbol>`` — continue
to work byte-identical to the pre-package shape.

Layout:

- ``_shared.py`` — cross-slice plumbing: ``ScheduledActivateError``,
  ``lock_session``, ``_ensure_aware_utc``, ``_OFFSET_MAX_MAGNITUDE``.
- ``_duration.py`` — ISO 8601 duration parsing + anchor / offset
  resolver (``parse_iso_duration``, ``resolve_offset``).
- ``_activation.py`` — scheduled ``validated → ready`` trigger +
  retry-counter + ``parse_and_validate_scheduled_activate_at``.
- ``_invites.py`` — auto-send invitations trigger +
  ``parse_and_validate_invite_offsets``.
- ``_reminders.py`` — auto-send reminders trigger +
  ``parse_and_validate_reminder_offsets``.
- ``_release.py`` — responses-release window parsers +
  ``validate_schedule_ordering`` (cross-field ordering).

The :func:`observe_scheduled_events` orchestrator lives here in
``__init__`` — it dispatches across the three trigger sub-modules
without depending on any of them; keeping it at the package root
avoids a circular import.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import audit
from app.services import session_lifecycle as lifecycle  # noqa: F401 — re-export for legacy ``monkeypatch.setattr("app.services.scheduled_events.lifecycle.activate_session", …)`` paths

# Private names (single underscore) are part of the byte-stable
# re-export wall: a handful of tests and one Alembic migration reach
# in via ``scheduled_events._<name>``. The F401 noqa markers
# acknowledge that these imports are deliberate re-exports rather
# than dead code; the public names below carry ``__all__`` instead.
from ._activation import (
    _ACTIVATION_MAX_RETRIES,  # noqa: F401
    _count_recent_retries,  # noqa: F401
    _emit_activation_skipped,  # noqa: F401
    _emit_activation_retry_or_failed,  # noqa: F401
    _observe_scheduled_activation,
    parse_and_validate_scheduled_activate_at,
)
from ._duration import (
    _ISO_DURATION_RE,  # noqa: F401
    parse_iso_duration,
    resolve_offset,
)
from ._invites import (
    _consumed_invite_offset_indices,  # noqa: F401
    _dispatch_pending_invitations,  # noqa: F401
    _observe_scheduled_invites,
    _resolve_invite_fires,  # noqa: F401
    parse_and_validate_invite_offsets,
)
from ._release import (
    _RELEASE_WINDOW_MAX,  # noqa: F401
    parse_and_validate_responses_release_at,
    parse_and_validate_responses_release_until,
    validate_schedule_ordering,
)
from ._reminders import (
    _consumed_reminder_offset_indices,  # noqa: F401
    _dispatch_scheduled_reminders,  # noqa: F401
    _observe_scheduled_reminders,
    _resolve_reminder_fires,  # noqa: F401
    parse_and_validate_reminder_offsets,
)
from ._shared import (
    _OFFSET_MAX_MAGNITUDE,  # noqa: F401
    ScheduledActivateError,
    _ensure_aware_utc,  # noqa: F401
    lock_session,
)


__all__ = [
    "ScheduledActivateError",
    "lock_session",
    "observe_scheduled_events",
    "parse_and_validate_invite_offsets",
    "parse_and_validate_reminder_offsets",
    "parse_and_validate_responses_release_at",
    "parse_and_validate_responses_release_until",
    "parse_and_validate_scheduled_activate_at",
    "parse_iso_duration",
    "resolve_offset",
    "validate_schedule_ordering",
]


log = logging.getLogger(__name__)

SCHEDULED_EVENT_FAILED = "session.scheduled_event_failed"


def observe_scheduled_events(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime | None = None,
    correlation_id: str | None = None,
    build_invite_url: Callable[[str], str] | None = None,
) -> None:
    """Lazy observer entry point — called from Session Home's GET, its
    only caller.

    Fires any scheduled-event triggers whose fire-time has passed
    and whose preconditions are met. Idempotent and concurrency-safe
    via :func:`lock_session` + each trigger's idempotency check.

    Triggers wired so far:

    - PR 1B — :func:`_observe_scheduled_activation`
    - PR 2A — :func:`_observe_scheduled_invites`
    - PR 3A — :func:`_observe_scheduled_reminders`

    ``build_invite_url`` is the URL builder consumed by the
    invite-dispatch path (``send_invitation`` in
    ``app.services.invitations``). The caller — typically the
    Session Home GET handler — passes
    ``lambda token: str(request.url_for("reviewer_invite", token=token))``.
    When omitted the invite trigger no-ops (a stand-alone
    background-worker dispatch path will plumb a deployment-base-URL
    closure here).

    The ``(db, session, now, correlation_id, …)`` contract is what
    each trigger consumes; ``now`` is resolved once up-front so all
    triggers in this pass see the same clock — and the catch-up
    ordering (past-due invites fire before activation in the same
    pass) is the natural order below.
    """
    current = now or datetime.now(timezone.utc)
    _run_guarded(
        db,
        session,
        trigger="invites",
        correlation_id=correlation_id,
        fire=lambda: _observe_scheduled_invites(
            db,
            session,
            now=current,
            correlation_id=correlation_id,
            build_invite_url=build_invite_url,
        ),
    )
    _run_guarded(
        db,
        session,
        trigger="activation",
        correlation_id=correlation_id,
        fire=lambda: _observe_scheduled_activation(
            db, session, now=current, correlation_id=correlation_id
        ),
    )
    _run_guarded(
        db,
        session,
        trigger="reminders",
        correlation_id=correlation_id,
        fire=lambda: _observe_scheduled_reminders(
            db,
            session,
            now=current,
            correlation_id=correlation_id,
            build_invite_url=build_invite_url,
        ),
    )


def _run_guarded(
    db: Session,
    session: ReviewSession,
    *,
    trigger: str,
    correlation_id: str | None,
    fire: Callable[[], None],
) -> None:
    """Run one trigger so that its failure never fails the page.

    Activation has its own retry and ``failed_persistent`` terminal
    state; invites and reminders do not yet (work in progress awaiting
    Azure, ``guide/post_azure_todo_checklist.md`` item 7). Until then an
    uncaught render, outbox or audit error would propagate out of this
    observer and fail the GET that ran it — Session Home, on every load.
    Here it is rolled back, logged and recorded as
    ``session.scheduled_event_failed``; the next visit tries again.

    An audit-schema error is re-raised: it only ever raises in strict
    mode, where it is the test suite's gate on event drift.
    """
    session_id = session.id
    try:
        fire()
    except audit.AuditDetailValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 — observer must keep page rendering
        db.rollback()
        log.exception(
            "Scheduled %s trigger failed for session %s", trigger, session_id
        )
        _record_failure(
            db,
            session_id=session_id,
            trigger=trigger,
            error_text=repr(exc)[:200],
            correlation_id=correlation_id,
        )


def _record_failure(
    db: Session,
    *,
    session_id: int,
    trigger: str,
    error_text: str,
    correlation_id: str | None,
) -> None:
    """Write ``session.scheduled_event_failed`` unless this trigger's
    latest one for the session already records the same error, so a
    failure repeated on every page load leaves one row per trigger
    rather than one per visit. A failure to write it is logged and
    rolled back; an audit-schema error is re-raised (see
    :func:`_run_guarded`)."""
    try:
        rows = db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == session_id,
                AuditEvent.event_type == SCHEDULED_EVENT_FAILED,
            )
            .order_by(AuditEvent.id.desc())
        ).scalars()
        for row in rows:
            detail = row.detail if isinstance(row.detail, dict) else {}
            context = detail.get("context") or {}
            if isinstance(context, dict) and context.get("trigger") == trigger:
                if detail.get("reason") == error_text:
                    return
                break
        review_session = db.get(ReviewSession, session_id)
        if review_session is None:
            return
        audit.write_event(
            db,
            event_type=SCHEDULED_EVENT_FAILED,
            summary=f"Scheduled {trigger} failed for {review_session.code}",
            actor_user_id=None,
            session=review_session,
            reason=error_text,
            context={"trigger": trigger},
            correlation_id=correlation_id,
        )
        db.commit()
    except audit.AuditDetailValidationError:
        raise
    except Exception:  # noqa: BLE001 — recording the failure must not fail the page
        db.rollback()
        log.exception(
            "Could not record the scheduled %s failure for session %s",
            trigger,
            session_id,
        )
