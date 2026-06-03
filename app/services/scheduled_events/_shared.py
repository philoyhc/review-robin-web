"""Cross-slice plumbing for the scheduled-events package.

The five concern-specific submodules (``_duration``, ``_activation``,
``_invites``, ``_reminders``, ``_release``) all read from here;
nothing here reads from them. Keeps the dependency graph acyclic
so the per-trigger observers can each lock the session row without
having to import siblings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


# Per spec/guide/segment_18G_scheduled_events.md Part 0b, the offset
# String(16) column is sized for a 10-day cap on any single offset.
# Enforced at the editor/validator level — the schema doesn't itself
# reject longer strings (`-P9999D` would fit in 16 chars but is
# operationally meaningless).
_OFFSET_MAX_MAGNITUDE = timedelta(days=10)


class ScheduledActivateError(ValueError):
    """Raised when a schedule-related form value fails parse / validation.

    The route layer converts to ``HTTPException(422, detail=str(exc))``.
    Shared across activation, invites, reminders, release-window, and
    cross-field ordering validators.
    """


def _ensure_aware_utc(value: datetime) -> datetime:
    """SQLite stores naive timestamps even with ``DateTime(timezone=True)``;
    treat them as UTC for comparison purposes."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def lock_session(db: Session, session: ReviewSession) -> ReviewSession:
    """``SELECT … FOR UPDATE`` the session row + return the (refreshed)
    row.

    Used by triggers to prevent two concurrent operator GETs from
    racing the same fire. The Postgres path takes a row-level lock;
    SQLite silently no-ops the ``FOR UPDATE`` (single-writer DB),
    which is acceptable for the dev loop.

    The caller is expected to follow with an **idempotency check**
    on the relevant schedule column inside the same transaction —
    e.g. ``if locked.scheduled_activate_at is None: return`` — so
    that a second racer sees the first racer's commit and bails.
    """
    return db.execute(
        select(ReviewSession)
        .where(ReviewSession.id == session.id)
        .with_for_update()
    ).scalar_one()
