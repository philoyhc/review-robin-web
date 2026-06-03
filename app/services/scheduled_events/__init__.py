"""Lazy observer for scheduled session-lifecycle events (Segment 18G).

Per ``spec/lifecycle.md`` §8.2 + §8.3: scheduled events fire on
operator GETs to session-related pages. Each trigger checks its
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

from datetime import datetime, timezone

from typing import Callable

from sqlalchemy.orm import Session

from app.db.models import ReviewSession
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


def observe_scheduled_events(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime | None = None,
    correlation_id: str | None = None,
    build_invite_url: Callable[[str], str] | None = None,
) -> None:
    """Lazy observer entry point — called from session-related GETs
    (Session Home, Operations pages, the Sessions lobby).

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
    _observe_scheduled_invites(
        db,
        session,
        now=current,
        correlation_id=correlation_id,
        build_invite_url=build_invite_url,
    )
    _observe_scheduled_activation(
        db, session, now=current, correlation_id=correlation_id
    )
    _observe_scheduled_reminders(
        db,
        session,
        now=current,
        correlation_id=correlation_id,
        build_invite_url=build_invite_url,
    )
