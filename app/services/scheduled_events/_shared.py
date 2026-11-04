"""Cross-slice plumbing for the scheduled-events package.

The five concern-specific submodules (``_duration``, ``_activation``,
``_invites``, ``_reminders``, ``_release``) all read from here;
nothing here reads from them. Keeps the dependency graph acyclic
so the per-trigger observers can each lock the session row without
having to import siblings.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from app.services.session_guard import (
    lock_session as lock_session,  # re-exported; moved for findings Bc4
)

if TYPE_CHECKING:
    from app.db.models import ReviewSession

# The helpers the sibling submodules import from here.
__all__ = [
    "ScheduledActivateError",
    "_OFFSET_MAX_MAGNITUDE",
    "_ensure_aware_utc",
    "_flushed_id",
    "_json_list",
    "_json_object",
    "lock_session",
]

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
        return value.replace(tzinfo=UTC)
    return value


def _flushed_id(review_session: ReviewSession) -> int | None:
    """``review_session.id``, which is ``None`` until the row is flushed
    although its mapping types it ``int``."""
    return review_session.id


def _json_object(value: object) -> dict[str, object] | None:
    """``value`` as a JSON object, or ``None`` when it is not one: audit
    ``detail`` and its ``context`` are JSON, and a legacy or hand-written
    row may hold any shape."""
    if not isinstance(value, dict):
        return None
    return cast(dict[str, object], value)


def _json_list(value: object) -> list[object] | None:
    """``value`` as a JSON array, or ``None`` when it is not one: a JSON
    column may hold a shape its mapping does not declare."""
    if not isinstance(value, list):
        return None
    return cast(list[object], value)
