"""Session lifecycle: status enum, readiness, activation, revert, instrument gates.

Segment 9.1 introduces the operator-controlled lifecycle that gates reviewer
write access. The canonical session status values live here as a Python enum
(no DB CHECK constraint); ``expired`` and ``archived`` are reserved for later
segments and not written by any 9.1 route.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Response,
    ReviewSession,
    User,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit


class SessionStatus(str, Enum):
    """Canonical session lifecycle values.

    9.5A adds ``validated`` between ``draft`` and ``ready``. ``expired`` and
    ``archived`` are reserved for later segments — recognised here so the
    string column is constrained at the application layer.
    """

    draft = "draft"
    validated = "validated"
    ready = "ready"
    expired = "expired"  # reserved (Segment 9.3+)
    archived = "archived"  # reserved (Segment 12+)


def is_ready(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.ready.value


def is_draft(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.draft.value


def is_validated(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.validated.value


def is_editable(review_session: ReviewSession) -> bool:
    """True when setup-mutating routes are allowed (``draft`` or ``validated``)."""
    return is_draft(review_session) or is_validated(review_session)


@dataclass
class ReadinessReport:
    """Activation gate input split by severity."""

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)

    @property
    def can_activate(self) -> bool:
        return not self.errors

    @property
    def has_non_blocking_findings(self) -> bool:
        """True iff there are warnings that require operator
        acknowledgment to activate. Info-severity issues are advisory
        only and don't trigger the acknowledgment ceremony — they were
        unused before Segment 11G PR B added the first info rule
        (``email_template.no_help_contact``)."""
        return bool(self.warnings)


def build_readiness_report(issues: list[ValidationIssue]) -> ReadinessReport:
    report = ReadinessReport()
    for issue in issues:
        if issue.severity is Severity.error:
            report.errors.append(issue)
        elif issue.severity is Severity.warning:
            report.warnings.append(issue)
        else:
            report.info.append(issue)
    return report


# --------------------------------------------------------------------------- #
# Activation / revert
# --------------------------------------------------------------------------- #


class LifecycleError(Exception):
    """Raised when an operator action violates lifecycle preconditions."""

    def __init__(self, message: str, *, code: str = "lifecycle_error") -> None:
        super().__init__(message)
        self.code = code


def mark_validated(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    report: ReadinessReport,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip ``draft → validated`` when the readiness report has no errors.

    Idempotent: a no-op when the session is already ``validated``. Raises
    ``LifecycleError`` if the session is not in ``draft``/``validated`` or
    if the report still has blocking errors. D3: warnings are implicitly
    acknowledged at the moment of transition.
    """
    if is_validated(review_session):
        return review_session
    if not is_draft(review_session):
        raise LifecycleError(
            f"Session is {review_session.status}, can only mark validated from draft",
            code="not_draft",
        )
    if not report.can_activate:
        raise LifecycleError(
            f"Cannot mark validated: {len(report.errors)} blocking error(s)",
            code="has_errors",
        )

    review_session.status = SessionStatus.validated.value
    db.flush()
    audit.write_event(
        db,
        event_type="session.validated",
        summary=f"Session {review_session.code} marked validated",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            warnings=len(report.warnings),
            info=len(report.info),
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def invalidate_if_validated(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    reason: str,
    correlation_id: str | None = None,
) -> None:
    """Idempotent ``validated → draft`` flip used by setup-mutating services.

    No-op for any other status (``draft``, ``ready``, ``expired``,
    ``archived``). Mutating services call this at their entry point so
    the ``validated → draft`` invariant is enforced where the mutation
    happens, not where the request happens — a route that forgets to
    wrap its service call no longer silently breaks the invariant.

    Visibility-when-closed services (``bulk_set_visibility``,
    ``set_responses_visible_when_closed``) deliberately do **not** call
    this helper: ``responses_visible_when_closed`` is a display flag
    that doesn't affect the validation snapshot. See ``docs/status.md``.
    """
    if is_validated(review_session):
        invalidate_session(
            db,
            review_session=review_session,
            user=user,
            reason=reason,
            correlation_id=correlation_id,
        )


def invalidate_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    reason: str,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip ``validated → draft`` after a setup-mutating action.

    No-op if the session is already ``draft``. Raises ``LifecycleError`` if
    the session is in any other status (e.g. ``ready``) — those routes
    should reject earlier via the editable-state gate.
    """
    if is_draft(review_session):
        return review_session
    if not is_validated(review_session):
        raise LifecycleError(
            f"Session is {review_session.status}, can only invalidate from validated",
            code="not_validated",
        )

    review_session.status = SessionStatus.draft.value
    db.flush()
    audit.write_event(
        db,
        event_type="session.invalidated",
        summary=f"Session {review_session.code} invalidated ({reason})",
        actor_user_id=user.id,
        session=review_session,
        reason=reason,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def activate_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    report: ReadinessReport,
    acknowledge_warnings: bool,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip session to ``ready`` and open every instrument.

    Requires the session to be in ``validated`` (T2). Raises ``LifecycleError``
    if the readiness report has errors, or if it has warnings/info and the
    operator did not pass ``acknowledge_warnings``.
    """
    if not is_validated(review_session):
        raise LifecycleError(
            f"Session is {review_session.status}, can only activate from validated",
            code="not_validated",
        )
    if not report.can_activate:
        raise LifecycleError(
            f"Cannot activate: {len(report.errors)} blocking error(s)",
            code="has_errors",
        )
    if report.has_non_blocking_findings and not acknowledge_warnings:
        raise LifecycleError(
            "Activation requires acknowledging warnings",
            code="needs_acknowledge",
        )

    prev_status = review_session.status
    review_session.status = SessionStatus.ready.value
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    for instrument in instruments:
        instrument.accepting_responses = True
        instrument.deadline_closed_at = None
    db.flush()

    audit.write_event(
        db,
        event_type="session.activated",
        summary=f"Session {review_session.code} activated",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            warnings=len(report.warnings),
            info=len(report.info),
            instruments=len(instruments),
        ),
        context={
            "prev_status": prev_status,
            "override_warnings": bool(report.has_non_blocking_findings),
        },
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def revert_session_to_draft(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    confirm: bool,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip ready→draft, close all instruments, preserve responses."""
    if not is_ready(review_session):
        raise LifecycleError(
            f"Session is {review_session.status}, can only revert from ready",
            code="not_ready",
        )
    if not confirm:
        raise LifecycleError(
            "Revert requires the confirm checkbox",
            code="needs_confirm",
        )

    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    closed_instrument_ids: list[int] = []
    for instrument in instruments:
        if instrument.accepting_responses:
            closed_instrument_ids.append(instrument.id)
        instrument.accepting_responses = False

    response_count = len(
        list(
            db.execute(
                select(Response.id)
                .join(Assignment, Assignment.id == Response.assignment_id)
                .where(Assignment.session_id == review_session.id)
            ).scalars()
        )
    )
    review_session.status = SessionStatus.draft.value
    db.flush()

    audit.write_event(
        db,
        event_type="session.reverted_to_draft",
        summary=f"Session {review_session.code} reverted to draft",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            closed_instruments=len(closed_instrument_ids),
            responses_at_revert=response_count,
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


# --------------------------------------------------------------------------- #
# Per-instrument controls
# --------------------------------------------------------------------------- #


def open_instrument(
    db: Session,
    *,
    instrument: Instrument,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
    now: datetime | None = None,
) -> Instrument:
    """Set ``accepting_responses=true``. Requires session ready and pre-deadline."""
    if not is_ready(review_session):
        raise LifecycleError(
            "Cannot open an instrument while session is not ready",
            code="session_not_ready",
        )
    current = now or datetime.now(timezone.utc)
    if review_session.deadline is not None and current >= _aware(
        review_session.deadline
    ):
        raise LifecycleError(
            "Cannot open an instrument past the session deadline",
            code="deadline_passed",
        )

    if not instrument.accepting_responses:
        instrument.accepting_responses = True
        instrument.deadline_closed_at = None
        db.flush()
        audit.write_event(
            db,
            event_type="instrument.opened",
            summary=f"Instrument {instrument.name} opened",
            actor_user_id=user.id,
            session=review_session,
            refs={"instrument_id": instrument.id},
            correlation_id=correlation_id,
        )
    db.commit()
    db.refresh(instrument)
    return instrument


def close_instrument(
    db: Session,
    *,
    instrument: Instrument,
    review_session: ReviewSession,
    user: User,
    reason: str = "manual",
    correlation_id: str | None = None,
) -> Instrument:
    """Set ``accepting_responses=false``. Idempotent if already closed."""
    if instrument.accepting_responses:
        instrument.accepting_responses = False
        db.flush()
        audit.write_event(
            db,
            event_type="instrument.closed",
            summary=f"Instrument {instrument.name} closed ({reason})",
            actor_user_id=user.id,
            session=review_session,
            refs={"instrument_id": instrument.id},
            reason=reason,
            correlation_id=correlation_id,
        )
    db.commit()
    db.refresh(instrument)
    return instrument


def set_responses_visible_when_closed(
    db: Session,
    *,
    instrument: Instrument,
    review_session: ReviewSession,
    user: User,
    visible: bool,
    correlation_id: str | None = None,
) -> Instrument:
    # #16 — visibility-when-closed is a display flag, not part of the
    # validation snapshot. Deliberately does NOT call
    # ``invalidate_if_validated``.
    instrument.responses_visible_when_closed = bool(visible)
    db.flush()
    db.commit()
    db.refresh(instrument)
    return instrument


# --------------------------------------------------------------------------- #
# Acceptance predicate + lazy deadline observer
# --------------------------------------------------------------------------- #


def _aware(value: datetime) -> datetime:
    """Treat naive datetimes as UTC for comparison (SQLite-stored timestamps)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def session_accepts_responses(
    review_session: ReviewSession,
    instrument: Instrument,
    *,
    now: datetime | None = None,
) -> bool:
    if not is_ready(review_session):
        return False
    if not instrument.accepting_responses:
        return False
    if review_session.deadline is not None:
        current = now or datetime.now(timezone.utc)
        if current >= _aware(review_session.deadline):
            return False
    return True


def observe_deadline(
    db: Session,
    review_session: ReviewSession,
    *,
    now: datetime | None = None,
    correlation_id: str | None = None,
) -> int:
    """Lazy deadline-close. Idempotent.

    Closes any instruments still ``accepting_responses`` once the session
    deadline has passed and stamps ``deadline_closed_at``. Emits one
    ``instrument.closed reason=deadline`` audit event per transition.
    Returns the number of instruments closed by this call.

    ``correlation_id`` is the request-scoped UUID minted by the
    ``request_correlation_id`` dependency; threading it through here is
    the only way to trace which reviewer's GET (or operator's GET)
    tripped the close, since the close itself runs anonymously
    (``actor_user_id=None``).
    """
    if review_session.deadline is None:
        return 0
    current = now or datetime.now(timezone.utc)
    if current < _aware(review_session.deadline):
        return 0

    instruments = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id,
                Instrument.accepting_responses.is_(True),
                Instrument.deadline_closed_at.is_(None),
            )
        ).scalars()
    )
    if not instruments:
        return 0

    closed = 0
    for instrument in instruments:
        instrument.accepting_responses = False
        instrument.deadline_closed_at = current
        audit.write_event(
            db,
            event_type="instrument.closed",
            summary=f"Instrument {instrument.name} closed (deadline)",
            actor_user_id=None,
            session=review_session,
            refs={"instrument_id": instrument.id},
            reason="deadline",
            context={"deadline": review_session.deadline.isoformat()},
            correlation_id=correlation_id,
        )
        closed += 1
    db.flush()
    db.commit()
    return closed


# --------------------------------------------------------------------------- #
# Helpers used by edit-lock + ack flows
# --------------------------------------------------------------------------- #


def session_has_responses(db: Session, review_session: ReviewSession) -> bool:
    """True iff any Response row exists under any of this session's assignments."""
    row = db.execute(
        select(Response.id)
        .join(Assignment, Assignment.id == Response.assignment_id)
        .where(Assignment.session_id == review_session.id)
        .limit(1)
    ).first()
    return row is not None


def assert_status_draft(review_session: ReviewSession) -> None:
    """Raise LifecycleError if session is not in draft (used by edit-lock)."""
    if not is_draft(review_session):
        raise LifecycleError(
            "Session is locked while status is not draft",
            code="locked",
        )


__all__ = [
    "SessionStatus",
    "ReadinessReport",
    "LifecycleError",
    "is_draft",
    "is_ready",
    "is_validated",
    "is_editable",
    "build_readiness_report",
    "mark_validated",
    "invalidate_if_validated",
    "invalidate_session",
    "activate_session",
    "revert_session_to_draft",
    "open_instrument",
    "close_instrument",
    "set_responses_visible_when_closed",
    "session_accepts_responses",
    "observe_deadline",
    "session_has_responses",
    "assert_status_draft",
]
