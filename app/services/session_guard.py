"""The session-row lock, and the lifecycle-state gate decided under it.

A service that writes a session's setup, roster, instruments, schedule
or lifecycle starts here, so the state it is gated on is the state as
committed rather than as loaded with the request (findings Bc3, Bc4;
``guide/archive/segment_19U_post_assessment_7oct.md`` Item 1 adopts it service
by service).

Nothing here imports another service: ``session_lifecycle`` and
``scheduled_events`` both build on this module, and ``LifecycleError``
lives here so ``session_lifecycle`` can re-export it without a cycle.
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
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


#: How long a request waits for another's session lock before it gives
#: up with :class:`SessionBusy` (author, 2026-11-01; `docs/database.md`):
#: long enough to ride out a normal save or import, far inside the
#: gateway's 120 s request limit. Postgres only; SQLite never waits.
LOCK_TIMEOUT_MS = 5000

#: Postgres's SQLSTATE for ``lock_timeout`` expiring (``lock_not_available``).
_LOCK_NOT_AVAILABLE = "55P03"

BUSY_MESSAGE = (
    "Someone else is changing this session right now. "
    "Try again in a moment."
)


class SessionBusy(Exception):
    """Another request held the session lock for longer than
    :data:`LOCK_TIMEOUT_MS`. Rendered as a 409 by the app-level handler
    (``app/web/error_handlers.py``). Not a :class:`SessionStateConflict`:
    the state did not refuse, so the routes that turn a state refusal
    into their own message must not catch it."""

    def __init__(self) -> None:
        super().__init__(BUSY_MESSAGE)


def lock_session(
    db: Session, session: ReviewSession, *, shared: bool = False
) -> ReviewSession:
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

    ``shared`` takes ``FOR SHARE`` instead: it still holds off every
    exclusive locker (the transitions, the scheduled passes) until the
    caller commits, but two shared lockers do not wait on each other.
    Only for a caller that never writes the session row nor locks it
    exclusively later in the same transaction, which would deadlock
    against another shared holder doing the same.
    """
    # Flush first: ``populate_existing`` overwrites the object with the
    # row, and the app's sessions do not autoflush, so an unflushed edit
    # would otherwise be silently dropped.
    db.flush()
    statement = (
        select(ReviewSession)
        .where(ReviewSession.id == session.id)
        .with_for_update(read=shared, key_share=not shared)
        .execution_options(populate_existing=True)
    )
    if db.get_bind().dialect.name != "postgresql":
        return db.execute(statement).scalar_one()
    # Bound the wait for this lock alone (`docs/database.md`). Inside a
    # savepoint, so a timeout rolls back only the attempt and the caller's
    # transaction stays usable; the setting is put back afterwards so
    # later statements in the transaction wait as they did before.
    try:
        with db.begin_nested():
            before = db.execute(text("SELECT current_setting('lock_timeout')")).scalar_one()
            db.execute(
                text("SELECT set_config('lock_timeout', :value, true)"),
                {"value": f"{LOCK_TIMEOUT_MS}ms"},
            )
            locked = db.execute(statement).scalar_one()
            db.execute(
                text("SELECT set_config('lock_timeout', :value, true)"),
                {"value": before},
            )
    except OperationalError as exc:
        if getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE:
            raise SessionBusy() from exc
        raise
    return locked


def require_state(
    db: Session,
    session: ReviewSession,
    allowed: Callable[[ReviewSession], bool],
    *,
    code: str,
    message: str,
    shared: bool = False,
) -> ReviewSession:
    """Lock and re-read the session, then refuse unless ``allowed``.

    ``message`` may name ``{status}``, filled from the re-read row so
    the refusal reports the state that actually refused it. ``shared``
    is :func:`lock_session`'s."""
    # The two-argument call for the default lock, which every other
    # caller and its test spies use.
    locked = (
        lock_session(db, session, shared=True)
        if shared
        else lock_session(db, session)
    )
    if not allowed(locked):
        raise SessionStateConflict(
            message.format(status=locked.status), code=code
        )
    return locked
