"""Sessions linked to another application (segment 23E).

A session another Cordware application created through the handoff
(`spec/handoffs.md`) carries ``ReviewSession.linked_app``, naming the
application. What a link changes is the application's profile here, in
code, so a change reaches every linked session on deploy. A value with no
profile reads as native. Only the handoff's create sets the mark;
:func:`unlink` clears it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit

UNLINKED = "session.unlinked"


@dataclass(frozen=True)
class LinkedProfile:
    """One application's profile: its key, the name Review Robin shows,
    and what it turns off. ``shows_results`` is where results are seen
    instead (the visibility card's *See in …*)."""

    key: str
    name: str
    shows_results: str
    release_off: bool = True
    observers_off: bool = True


#: Every application a session may link to, by the ``source_app`` its
#: handoff sends. Utilities' interop proof of concept links as Apply Desk
#: will, so the profile can be tried before Apply Desk sends (author,
#: 2026-11-15).
LINKED_APPS: dict[str, LinkedProfile] = {
    "applydesk": LinkedProfile("applydesk", "Apply Desk", "Apply Desk"),
    "utilities": LinkedProfile("utilities", "Utilities (interop proof of concept)", "Utilities"),
}


def profile_for(source_app: str) -> LinkedProfile | None:
    """The profile a handoff's ``source_app`` links to, or None."""
    return LINKED_APPS.get(source_app)


def profile_of(review_session: ReviewSession) -> LinkedProfile | None:
    """The session's profile, or None for a native session."""
    key = review_session.linked_app
    return LINKED_APPS.get(key) if key else None


def unlink(
    db: Session, *, review_session: ReviewSession, user: User, correlation_id: str | None
) -> bool:
    """Clear the mark, audited; the session is native from then on.
    False when it was not linked (nothing written)."""
    was = review_session.linked_app
    if not was:
        return False
    review_session.linked_app = None
    audit.write_event(
        db,
        event_type=UNLINKED,
        summary=f"Session unlinked from {was}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"linked_app": [was, None]}),
        correlation_id=correlation_id,
    )
    db.commit()
    return True
