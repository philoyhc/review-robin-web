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
from app.services import directory_recheck

_COUNT_KEYS = (
    "directory_by_mail",
    "directory_by_upn",
    "directory_not_found",
    "directory_ambiguous",
    "directory_not_checked",
)

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
    #: Of the not-checked rows, those a replace left on the account an
    #: earlier import bound them to (assessment 2026-11-02, M1).
    kept: int = 0
    #: Why addresses went unchecked, as the import recorded it (segment
    #: 20G), in words for the line; ``None`` for an import that recorded
    #: none (every address answered, or one from before 20G).
    reason: str | None = None
    #: The line reports the card's recheck (segment 20I Item 1), not an
    #: import; ``held`` counts rows found on an account another row holds.
    recheck: bool = False
    held: int = 0

    @property
    def checked(self) -> bool:
        """Whether the directory answered for any address at all."""
        return (self.by_mail + self.by_upn + self.not_found + self.ambiguous + self.held) > 0


def last_directory_check(
    db: Session, review_session: ReviewSession, kind: str
) -> DirectoryCheck | None:
    """The latest ``kind`` import's or recheck's directory counts, or
    ``None``: whichever ran last (segment 20I Item 1)."""
    event_type = _EVENT.get(kind)
    if event_type is None:
        return None
    recheck_type = directory_recheck.EVENTS[kind]
    event = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type.in_((event_type, recheck_type)),
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    counts = (event.detail or {}).get("counts", {}) if event is not None else {}
    if "directory_not_checked" not in counts:
        return None
    # An import with no address to check (anonymous identifiers only)
    # has nothing to report (Codex, #3429).
    if not any(counts.get(k, 0) for k in (*_COUNT_KEYS, "directory_held")):
        return None
    return DirectoryCheck(
        at=event.created_at,
        by_mail=counts.get("directory_by_mail", 0),
        by_upn=counts.get("directory_by_upn", 0),
        not_found=counts.get("directory_not_found", 0),
        ambiguous=counts.get("directory_ambiguous", 0),
        not_checked=counts.get("directory_not_checked", 0),
        kept=counts.get("directory_kept", 0),
        reason=_reason_text(((event.detail or {}).get("context") or {}).get("directory_unchecked")),
        recheck=event.event_type == recheck_type,
        held=counts.get("directory_held", 0),
    )


def unmatched_count(db: Session, review_session: ReviewSession, kind: str) -> int:
    """How many rows the Upload card's recheck button names (segment 20I
    Item 1): `directory_recheck.unmatched_rows`."""
    if kind not in directory_recheck.ROSTERS:
        return 0
    # Under symmetric review the reviewees mirror the reviewers, and a
    # Reviewers recheck binds both; the Reviewees one is refused.
    if kind == "reviewees" and review_session.symmetric_review:
        return 0
    return len(directory_recheck.unmatched_rows(db, session_id=review_session.id, kind=kind))


#: The card's words for why addresses went unchecked (segment 20G), by
#: the reason the import recorded (`directory_accounts.unchecked_reason`).
_REASONS = {
    "no_token": "this sign-in carries no directory access",
    "forbidden": "the directory refused this account's access",
    "unauthorized": "the sign-in to the directory had expired",
    "throttled": "the directory was busy",
    "timeout": "the check ran out of time",
}


def _reason_text(reason: object) -> str | None:
    """The line's words for ``reason``; any other failure kind reads as
    the directory not answering."""
    if not reason:
        return None
    return _REASONS.get(str(reason), "the directory did not answer")
