"""The session-row lock, and the lifecycle-state gate decided under it.

Every service that writes a session's setup, roster, instruments,
schedule or lifecycle starts here, so the state it is gated on is the
state as committed rather than as loaded with the request (findings
Bc3, Bc4; ``guide/segment_19U_post_assessment_7oct.md`` Item 1).

Nothing here imports another service: ``session_lifecycle`` and
``scheduled_events`` both build on this module, and ``LifecycleError``
lives here so ``session_lifecycle`` can re-export it without a cycle.
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


class LifecycleError(Exception):
    """Raised when an operator action violates lifecycle preconditions."""

    def __init__(self, message: str, *, code: str = "lifecycle_error") -> None:
        super().__init__(message)
        self.code = code


class SessionStateConflict(LifecycleError):
    """A write refused because the session's state, re-read under the
    lock, does not allow it. Rendered as a 409 by the app-level handler
    (``app/web/error_handlers.py``), the status the routes' own gates
    have always answered with."""


def lock_session(db: Session, session: ReviewSession) -> ReviewSession:
    """``SELECT … FOR NO KEY UPDATE`` the session row + return it,
    refreshed from the database.

    Taken first by the scheduled-event triggers, by the lifecycle
    transitions, and through :func:`require_state` by the saves gated on
    the session's state, so each decides from what the others last
    committed (findings Bc3, Bc4). The Postgres path takes a row-level
    lock; SQLite silently no-ops it (single-writer DB), which is
    acceptable for the dev loop.

    ``populate_existing`` re-reads the row under the lock: the caller's
    object is the identity-mapped one, and without it the values would
    be the ones loaded before the lock, so a racer that committed first
    would go unseen. ``FOR NO KEY UPDATE`` (``key_share``) still
    serializes two lockers but, unlike ``FOR UPDATE``, does not block
    other transactions' foreign-key inserts (audit rows, tags) on the
    session.

    Taking it again in the same transaction is cheap and re-reads the
    row; the lock is held until the transaction commits or rolls back.
    """
    # Flush first: ``populate_existing`` overwrites the object with the
    # row, and the app's sessions do not autoflush, so an unflushed edit
    # would otherwise be silently dropped.
    db.flush()
    return db.execute(
        select(ReviewSession)
        .where(ReviewSession.id == session.id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    ).scalar_one()


def require_state(
    db: Session,
    session: ReviewSession,
    allowed: Callable[[ReviewSession], bool],
    *,
    code: str,
    message: str,
) -> ReviewSession:
    """Lock and re-read the session, then refuse unless ``allowed``.

    ``message`` may name ``{status}``, filled from the re-read row so
    the refusal reports the state that actually refused it."""
    locked = lock_session(db, session)
    if not allowed(locked):
        raise SessionStateConflict(
            message.format(status=locked.status), code=code
        )
    return locked
