"""The in-app clock (segment 14E): one pass over the sessions whose timed
steps are due, so they happen on time with no page view.

A pass fires what an operator set, and nothing else
(`guide/interoperability.md` §2): a scheduled activation whose Start has
passed, the close of an open session past its end (End, or with no End,
Release from: ``session_lifecycle.review_end``), and the release window's
start and end stamps. It sends no mail: invites and reminders
stay with ``RRW_SCHEDULED_SEND`` (off until 14G), and even on, the clock
passes no invite-URL builder until 14G gives it one.

The page-view trigger (``observe_scheduled_events_on_load``) stays as a
backstop. Both run the same services under the per-session lock, so a
step reached by both happens once; an event the clock writes carries
``context.fired_by = "clock"`` (``audit.fired_by``).

**One pass at a time.** On Postgres the pass takes a transaction-level
advisory lock on :data:`LOCK_KEY` and skips when another process holds
it. SQLite (local, tests) takes no lock: one process.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import audit
from app.services import session_lifecycle as lifecycle
from app.services.session_guard import SessionBusy

from ._release import STAMP_GRACE

_log = logging.getLogger(__name__)

#: RRW's own advisory-lock key for the clock's pass, so another mounted
#: application's clock never contends with it (segment 14E;
#: `guide/interoperability.md` §2). The bytes of "RRWclock".
LOCK_KEY = 0x5252_5763_6C6F_636B


def _take_lock(db: Session) -> bool:
    """The pass's advisory lock: held to the end of the transaction on
    Postgres, always granted elsewhere."""
    if db.get_bind().dialect.name != "postgresql":
        return True
    return bool(
        db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY}).scalar()
    )


def due_session_ids(db: Session, *, now: datetime) -> list[int]:
    """Sessions with a timed step due: a scheduled Start that has passed,
    an open session past its end (End, or with no End, Release from), or
    a release-window moment crossed within ``STAMP_GRACE`` on an expired
    session (the window opens on no other). Archived sessions are left
    out.

    A Start whose last activation attempt failed within
    :data:`RETRY_SPACING` waits, so retries keep their spacing on the
    clock rather than spending all three in a few passes; the spacing
    holds back that Start only, never a deadline or release step due on
    the same session (Codex, #3579)."""
    since = now - STAMP_GRACE
    live = ReviewSession.status != lifecycle.SessionStatus.archived.value
    starts = db.execute(
        select(ReviewSession.id).where(live, ReviewSession.scheduled_activate_at <= now)
    ).scalars()
    others = db.execute(
        select(ReviewSession.id).where(
            live,
            or_(
                # An open session past its end, instruments open or not:
                # End, or with no End, Release from (`review_end`) closes
                # it (segment 14E).
                (ReviewSession.status == lifecycle.SessionStatus.ready.value)
                & or_(
                    ReviewSession.deadline <= now,
                    ReviewSession.deadline.is_(None)
                    & (ReviewSession.responses_release_at <= now),
                ),
                (ReviewSession.status == lifecycle.SessionStatus.expired.value)
                & or_(
                    ReviewSession.responses_release_at.between(since, now),
                    ReviewSession.responses_release_until.between(since, now),
                ),
            ),
        )
    ).scalars()
    due = set(others)
    due.update(i for i in starts if i not in due and not _retried_recently(db, i, now=now))
    return sorted(due)


#: The least time between two activation attempts the clock makes after
#: a failure (segment 14E). The page-view trigger keeps its own pace.
RETRY_SPACING = timedelta(minutes=15)


def _retried_recently(db: Session, session_id: int, *, now: datetime) -> bool:
    """Whether this session's last scheduled-activation retry is younger
    than :data:`RETRY_SPACING`; true only for a session mid-retry."""
    last = db.execute(
        select(AuditEvent.created_at)
        .where(
            AuditEvent.session_id == session_id,
            AuditEvent.event_type == "session.scheduled_activation_retry",
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar()
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return now - last < RETRY_SPACING


def run_pass(
    session_factory: Callable[[], AbstractContextManager[Session]],
    *,
    now: datetime | None = None,
    stop: threading.Event | None = None,
) -> int:
    """One pass of the clock. ``stop``, once set, ends the pass after the
    session in hand (shutdown). Returns how many sessions it visited, or
    ``-1`` when another process held the pass. A session that fails is
    logged and rolled back, and the pass goes on to the next."""
    # Imported here: the package's ``__init__`` imports this module.
    from app.services.scheduled_events import observe_scheduled_events

    current = now or datetime.now(UTC)
    with session_factory() as gate:
        if not _take_lock(gate):
            return -1
        ids = due_session_ids(gate, now=current)
        visited = 0
        for session_id in ids:
            if stop is not None and stop.is_set():
                break
            # Each session in its own database session, so one failure
            # rolls back only its own work.
            with session_factory() as db, audit.fired_by("clock"):
                try:
                    review_session = db.get(ReviewSession, session_id)
                    if review_session is None:
                        continue
                    # Activation, End's close, Release from's close and the
                    # release stamps, as a page view runs them.
                    observe_scheduled_events(db, review_session, now=current)
                    db.commit()
                    visited += 1
                except SessionBusy:
                    # Contention, not a failure: the next pass tries again.
                    db.rollback()
                    _log.info("scheduled clock: session %s busy; next pass", session_id)
                except Exception:
                    db.rollback()
                    _log.exception("scheduled clock: session %s failed", session_id)
        # Ends the transaction, releasing the advisory lock.
        gate.commit()
    return visited


async def run_forever(
    session_factory: Callable[[], AbstractContextManager[Session]],
    *,
    interval: float,
    stop: threading.Event,
) -> None:
    """The loop RRW's lifespan starts: wait ``interval`` seconds, run a
    pass in a worker thread, repeat until ``stop`` is set. The first pass
    waits too, so a start-up is not slowed. A pass that raises is logged
    and the loop goes on."""
    while not stop.is_set():
        # Waits in a worker thread on ``stop`` itself, so a shutdown wakes
        # it at once rather than after the interval.
        if await asyncio.to_thread(stop.wait, interval):
            break
        try:
            visited = await asyncio.to_thread(run_pass, session_factory, stop=stop)
        except Exception:
            _log.exception("scheduled clock: pass failed")
            continue
        if visited > 0:
            _log.info(
                "scheduled clock: pass visited %s session(s)",
                visited,
                extra={"event": "scheduled_clock.pass", "visited": visited},
            )
