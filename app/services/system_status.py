"""What the System Status tab reports beyond the clock's own record
(segment 22G Item 1): what the clock will do next across the workspace
(the Due next card), and this instance (version, start, database).

Due now is the clock's own pick (``scheduled_events.due_session_ids``),
and the next moments follow the rules that pick applies, so the card and
the clock agree about what is due; archived sessions are left out, as
there. Read-only: nothing here fires a step.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession
from app.db.schema_head import SCHEMA_HEAD
from app.services import session_lifecycle as lifecycle
from app.services.scheduled_events import due_session_ids

#: How far back the card lists activations that failed for good.
FAILED_ACTIVATION_WINDOW = timedelta(days=7)

ACTIVATION_FAILED_PERSISTENT = "session.scheduled_activation_failed_persistent"


@dataclasses.dataclass(frozen=True)
class SessionAt:
    """A session and the moment that concerns it."""

    session_id: int
    public_id: str
    name: str
    code: str
    at: datetime | None = None


@dataclasses.dataclass(frozen=True)
class DueNext:
    next_start: SessionAt | None
    next_close: SessionAt | None
    next_release_stamp: SessionAt | None
    due_now: list[SessionAt]
    failed_activations: list[SessionAt]


def _utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _at(rs: ReviewSession, at: datetime | None) -> SessionAt:
    return SessionAt(session_id=rs.id, public_id=rs.public_id, name=rs.name, code=rs.code, at=at)


def _earliest(candidates: list[SessionAt]) -> SessionAt | None:
    timed = [c for c in candidates if c.at is not None]
    return min(timed, key=lambda c: (c.at, c.session_id)) if timed else None


def due_next(db: Session, *, now: datetime | None = None) -> DueNext:
    current = now or datetime.now(UTC)
    live = ReviewSession.status != lifecycle.SessionStatus.archived.value

    # A scheduled Start still to come (one that has passed is due now).
    starts = db.execute(
        select(ReviewSession).where(live, ReviewSession.scheduled_activate_at > current)
    ).scalars()
    next_start = _earliest([_at(rs, _utc(rs.scheduled_activate_at)) for rs in starts])

    # An open session's close: End, or with no End, Release from.
    open_sessions = db.execute(
        select(ReviewSession).where(
            ReviewSession.status == lifecycle.SessionStatus.ready.value,
            or_(ReviewSession.deadline > current, ReviewSession.responses_release_at > current),
        )
    ).scalars()
    closes = [_at(rs, lifecycle.review_end(rs)) for rs in open_sessions]
    next_close = _earliest([c for c in closes if c.at is not None and c.at > current])

    # The release window's opening or closing stamp, by the clock's rule
    # (``_release._due_release_stamps``): a window stamps only from its
    # Release from, and closes only after it opens; a session stamps only
    # once ended, so a draft one, not yet run, is left out.
    windows = db.execute(
        select(ReviewSession).where(
            ReviewSession.status.in_(
                [lifecycle.SessionStatus.ready.value, lifecycle.SessionStatus.expired.value]
            ),
            ReviewSession.responses_release_at.is_not(None),
            or_(
                ReviewSession.responses_release_at > current,
                ReviewSession.responses_release_until > current,
            ),
        )
    ).scalars()
    stamps: list[SessionAt] = []
    for rs in windows:
        start = _utc(rs.responses_release_at)
        until = _utc(rs.responses_release_until)
        if start is None:
            continue
        if start > current:
            stamps.append(_at(rs, start))
        if until is not None and start < until and until > current:
            stamps.append(_at(rs, until))
    next_release_stamp = _earliest(stamps)

    # What the clock's next pass would pick: a session listed pass after
    # pass is not being moved.
    due_ids = due_session_ids(db, now=current)
    due_rows: list[ReviewSession] = (
        list(db.execute(select(ReviewSession).where(ReviewSession.id.in_(due_ids))).scalars())
        if due_ids
        else []
    )
    due_now = sorted((_at(rs, None) for rs in due_rows), key=lambda s: s.session_id)

    failed = db.execute(
        select(AuditEvent, ReviewSession)
        .join(ReviewSession, AuditEvent.session_id == ReviewSession.id)
        .where(
            live,
            AuditEvent.event_type == ACTIVATION_FAILED_PERSISTENT,
            AuditEvent.created_at >= current - FAILED_ACTIVATION_WINDOW,
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    ).all()
    failed_activations = [_at(rs, _utc(event.created_at)) for event, rs in failed]

    return DueNext(
        next_start=next_start,
        next_close=next_close,
        next_release_stamp=next_release_stamp,
        due_now=due_now,
        failed_activations=failed_activations,
    )


@dataclasses.dataclass(frozen=True)
class Instance:
    """This instance. ``schema_revision`` is ``None`` when the database
    records none (a schema built without Alembic, as the tests build
    it, or a read that failed)."""

    version: str
    dialect: str
    schema_revision: str | None
    schema_head: str

    @property
    def schema_current(self) -> bool:
        return self.schema_revision == self.schema_head


def _schema_revision(db: Session) -> str | None:
    try:
        # A nested transaction, so a missing table rolls back only this.
        with db.begin_nested():
            rows = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    except SQLAlchemyError:
        return None
    return ", ".join(sorted(rows)) or None


def instance(db: Session) -> Instance:
    return Instance(
        version=settings.app_version,
        dialect=db.get_bind().dialect.name,
        schema_revision=_schema_revision(db),
        schema_head=SCHEMA_HEAD,
    )
