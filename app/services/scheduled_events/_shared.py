"""Cross-slice plumbing for the scheduled-events package.

The five concern-specific submodules (``_duration``, ``_activation``,
``_invites``, ``_reminders``, ``_release``) all read from here;
nothing here reads from them. Keeps the dependency graph acyclic
so the per-trigger observers can each lock the session row without
having to import siblings.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.session_guard import lock_session  # noqa: F401 — re-exported; moved for findings Bc4


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
