"""Sessions linked to another application (segments 23E, 23F).

A session another Cordware application created through the handoff
(`spec/handoffs.md`) carries ``ReviewSession.linked_app``, naming the
application. What a link changes is the application's profile here, in
code, so a change reaches every linked session on deploy. A value with no
profile reads as native. Only the handoff's create sets the mark;
:func:`unlink` clears it.

**The switchboard** (segment 23F rung 2a): a profile is a set of named
:class:`Lock` values from one menu, and every gate asks :func:`locks`.
Another application with different needs is another profile entry, not
new code paths. Profiles stay in code: they decide what an operator may
not touch, so neither the database nor a bundle may set them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit

UNLINKED = "session.unlinked"


class Lock(StrEnum):
    """What a linked application can turn off in Review Robin. Each is
    checked where its surface is written (and hidden where it is shown);
    a lock no gate checks yet has no effect."""

    #: The release window: the application shows results (23E).
    RELEASE = "release"
    #: Observers, their roster and their pages (23E).
    OBSERVERS = "observers"
    #: The Session details card and the lobby's inline edits (23F).
    SESSION_DETAILS = "session_details"
    #: The Quick Setup card (23F).
    QUICK_SETUP = "quick_setup"
    #: Roster uploads, rows, directory add and tags (23F).
    ROSTERS = "rosters"
    #: The Settings import (23F).
    SETTINGS_IMPORT = "settings_import"
    #: Review Robin's email: templates, sends, the submit acknowledgement (23F).
    EMAIL = "email"
    #: The Invitations page's Send and Regenerate (23F).
    INVITATION_SEND = "invitation_send"
    #: Which instruments exist and their owned parts (23F).
    INSTRUMENT_STRUCTURE = "instrument_structure"


#: The session fields a linked application owns and re-sends (23F, the
#: author's lock list of 2026-11-16).
SESSION_FIELDS = frozenset(
    {
        "session.name",
        "session.code",
        "session.description",
        "session.display_timezone",
        "session.help_contact",
        "session.scheduled_activate_at",
        "session.deadline",
        "session.relationships_enabled",
        # The session's tags, every ``session_tags[N].tag`` row
        # (``linked_settings.TAGS``).
        "session_tags",
    }
)


@dataclass(frozen=True)
class LinkedProfile:
    """One application's profile: its key, the name Review Robin shows,
    where results are seen instead (the visibility card's *See in …*),
    what it locks, and the settings fields it owns."""

    key: str
    name: str
    shows_results: str
    locks: frozenset[Lock] = frozenset(Lock)
    owned_settings: frozenset[str] = field(default=SESSION_FIELDS)

    def has(self, lock: Lock | str) -> bool:
        """Whether the profile takes ``lock``; a template passes its
        value (``linked.has("release")``)."""
        return lock in self.locks


#: Every application a session may link to, by the ``source_app`` its
#: handoff sends. Apply Desk takes every lock. Utilities' interop proof of
#: concept links as Apply Desk will, so the profile can be tried before
#: Apply Desk sends (author, 2026-11-15), but keeps Review Robin's email
#: on (author, 2026-11-16), so a second profile proves the switchboard.
LINKED_APPS: dict[str, LinkedProfile] = {
    "applydesk": LinkedProfile("applydesk", "Apply Desk", "Apply Desk"),
    "utilities": LinkedProfile(
        "utilities",
        "Utilities",
        "Utilities",
        locks=frozenset(Lock) - {Lock.EMAIL, Lock.INVITATION_SEND},
    ),
}


def profile_for(source_app: str) -> LinkedProfile | None:
    """The profile a handoff's ``source_app`` links to, or None."""
    return LINKED_APPS.get(source_app)


def profile_of(review_session: ReviewSession) -> LinkedProfile | None:
    """The session's profile, or None for a native session."""
    key = review_session.linked_app
    return LINKED_APPS.get(key) if key else None


def locks(review_session: ReviewSession, lock: Lock) -> bool:
    """Whether the session's linked application takes ``lock``; False on
    a native session. The one check every gate asks."""
    profile = profile_of(review_session)
    return profile is not None and profile.has(lock)


def locks_named(review_session: ReviewSession, name: str) -> bool:
    """:func:`locks` by the lock's value, for a template
    (``session | linked_locks("email")``)."""
    return locks(review_session, Lock(name))


def off_message(review_session: ReviewSession, what: str) -> str:
    """The refusal naming the link: ``what`` is off on this session."""
    profile = profile_of(review_session)
    name = profile.name if profile else "another application"
    return f"{what} is off: this session is linked to {name}."


def linked_name(review_session: ReviewSession) -> str:
    """The linked application's name, or "" for a native session (the
    status row's *Linked* pill, a Jinja filter)."""
    profile = profile_of(review_session)
    return profile.name if profile else ""


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
