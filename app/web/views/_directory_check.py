"""What the latest roster import's directory check came to (segment 21F,
rung 4b): the counts its audit event records, for the Setup page's
import card to show.

Read from the event, not kept anywhere else: an import saves on submit
and redirects, so the page that follows reads what the save recorded.
An import that ran no check (one from before segment 21F) shows nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession

_EVENT = {
    "reviewers": "reviewers.imported",
    "reviewees": "reviewees.imported",
    "observers": "observers.imported",
}


@dataclass(frozen=True)
class DirectoryCheck:
    at: datetime
    by_mail: int
    by_upn: int
    not_found: int
    ambiguous: int
    not_checked: int

    @property
    def checked(self) -> bool:
        """Whether the directory answered for any address at all."""
        return (self.by_mail + self.by_upn + self.not_found + self.ambiguous) > 0


def last_directory_check(
    db: Session, review_session: ReviewSession, kind: str
) -> DirectoryCheck | None:
    """The latest ``kind`` import's directory counts, or ``None``."""
    event_type = _EVENT.get(kind)
    if event_type is None:
        return None
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == review_session.id, AuditEvent.event_type == event_type)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    counts = (event.detail or {}).get("counts", {}) if event is not None else {}
    if "directory_not_checked" not in counts:
        return None
    return DirectoryCheck(
        at=event.created_at,
        by_mail=counts.get("directory_by_mail", 0),
        by_upn=counts.get("directory_by_upn", 0),
        not_found=counts.get("directory_not_found", 0),
        ambiguous=counts.get("directory_ambiguous", 0),
        not_checked=counts.get("directory_not_checked", 0),
    )
