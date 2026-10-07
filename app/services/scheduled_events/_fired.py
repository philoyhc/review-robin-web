"""Auto-send entries already sent on their anchor (findings Bc1).

The invite and reminder observers record each entry they send or skip
by its list position on its anchor (``context.offset_index`` /
``context.offset`` / ``context.anchor_at`` on the
``session.scheduled_*_fired`` / ``_skipped`` audit rows), and never fire
a recorded position again on that anchor, whatever entry sits there.
So a save that would put a different entry on a recorded position is
refused, and a sent entry kept in place skips the lead-time floor
(``spec/lifecycle.md`` §8.2.6).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession

from ._shared import _ensure_aware_utc

_EVENT_TYPES = {
    "invite": (
        "session.scheduled_invites_fired",
        "session.scheduled_invites_skipped",
    ),
    "reminder": (
        "session.scheduled_reminders_fired",
        "session.scheduled_reminders_skipped",
    ),
}

#: Per kind: the column, the anchor's column, and the copy's names.
_LISTS = (
    ("invite", "invite_offsets", "scheduled_activate_at",
     "Auto-send invite", "Start"),
    ("reminder", "reminder_offsets", "deadline",
     "Auto-send reminder", "End"),
)


def split_offsets(raw: str | None) -> list[str]:
    """The entries of a comma-separated offsets box, as the parsers read
    them, before any of their rules runs."""
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _same_instant(a: datetime | None, b: datetime | None) -> bool:
    if a is None or b is None:
        return a is b
    return _ensure_aware_utc(a) == _ensure_aware_utc(b)


def fired_offsets(
    db: Session,
    review_session: ReviewSession,
    kind: str,
    anchor: datetime | None,
) -> dict[int, str]:
    """``{position: entry}`` for the ``kind`` ("invite" / "reminder")
    entries already sent or skipped on ``anchor``. Anchors compare as
    instants, so the record is found whatever offset the stored value
    was rendered with."""
    if anchor is None or review_session.id is None:
        return {}
    rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type.in_(_EVENT_TYPES[kind]),
        )
    ).scalars()
    fired: dict[int, str] = {}
    for row in rows:
        ctx = row.detail.get("context") if isinstance(row.detail, dict) else None
        if not isinstance(ctx, dict):
            continue
        try:
            recorded = datetime.fromisoformat(str(ctx.get("anchor_at")))
        except ValueError:
            continue
        if not _same_instant(recorded, anchor):
            continue
        index, entry = ctx.get("offset_index"), ctx.get("offset")
        if isinstance(index, int):
            # The observers dedupe on the position alone; a row without
            # its entry still consumes it.
            fired.setdefault(index, entry if isinstance(entry, str) else "")
    return fired


def offsets_lead_exempt(
    db: Session,
    review_session: ReviewSession,
    kind: str,
    anchor: datetime | None,
    *,
    anchor_unedited: bool,
) -> list[str]:
    """The ``aged_exempt`` list for an offsets parser: per position, the
    entry that may stay there past the lead-time floor — the stored one
    while the anchor is unedited (findings B4), and above it the one
    already sent there on ``anchor`` (findings Bc1)."""
    column = "invite_offsets" if kind == "invite" else "reminder_offsets"
    stored = (getattr(review_session, column) or []) if anchor_unedited else []
    fired = fired_offsets(db, review_session, kind, anchor)
    size = max([len(stored), *(index + 1 for index in fired)])
    exempt = [stored[i] if i < len(stored) else "" for i in range(size)]
    for index, entry in fired.items():
        exempt[index] = entry
    return exempt


def fired_offset_errors(
    db: Session,
    review_session: ReviewSession,
    *,
    scheduled_activate_at: datetime | None,
    invite_offsets: Sequence[str],
    deadline: datetime | None,
    reminder_offsets: Sequence[str],
) -> list[tuple[str, str]]:
    """``(column, message)`` for each list that would put a different
    entry on a position already sent or skipped, on the anchor the
    session will hold (findings Bc1, ruled 2026-10-07). A list whose
    entries and anchor both stay as stored is not checked, so a save
    that leaves the schedule alone is never refused over it."""
    proposed = {
        "invite_offsets": (list(invite_offsets), scheduled_activate_at),
        "reminder_offsets": (list(reminder_offsets), deadline),
    }
    errors: list[tuple[str, str]] = []
    for kind, column, anchor_column, label, anchor_label in _LISTS:
        entries, anchor = proposed[column]
        if entries == list(getattr(review_session, column) or []) and (
            _same_instant(anchor, getattr(review_session, anchor_column))
        ):
            continue
        fired = fired_offsets(db, review_session, kind, anchor)
        for index in sorted(fired):
            if index < len(entries) and entries[index] != fired[index]:
                errors.append((
                    column,
                    f"{label} {fired[index]} was already sent (or "
                    f"skipped) at position {index + 1} for this "
                    f"{anchor_label}, so {entries[index]} there would "
                    f"never be sent. Keep {fired[index]} at position "
                    f"{index + 1} and add new entries after it.",
                ))
                break
    return errors
