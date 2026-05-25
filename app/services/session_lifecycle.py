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
    AuditEvent,
    Instrument,
    Response,
    Reviewer,
    ReviewSession,
    User,
)
from app.logging_config import get_logger
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit

log = get_logger(__name__)


class SessionStatus(str, Enum):
    """Canonical session lifecycle values.

    9.5A adds ``validated`` between ``draft`` and ``ready``. ``expired`` and
    ``archived`` are reserved for later segments — recognised here so the
    string column is constrained at the application layer.

    **Enum vs. display label.** Operators see ``ready`` rendered as
    ``"Activated"`` everywhere in the UI — the enum reads as "ready
    to be activated" but the visible label communicates "currently
    running". The mapping lives in ``app.services.lifecycle_display``
    (Jinja filter ``lifecycle_label``); other values pass through with
    their first letter capitalised. Anything machine-facing (URL
    slugs, query params, API responses, log lines, DB values, CSS
    class names like ``pill-lifecycle-ready``) continues to use the
    raw enum strings. See ``spec/session_home.md`` for the rationale.
    """

    draft = "draft"
    validated = "validated"
    # Display label is "Activated" — see class docstring and
    # ``app.services.lifecycle_display``.
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
    user: User | None,
    report: ReadinessReport,
    acknowledge_warnings: bool,
    correlation_id: str | None = None,
    trigger: str = "operator",
) -> ReviewSession:
    """Flip session to ``ready`` and open every instrument.

    Requires the session to be in ``validated`` (T2). Raises ``LifecycleError``
    if the readiness report has errors, or if it has warnings/info and the
    operator did not pass ``acknowledge_warnings``.

    ``user`` is the operator who clicked Activate; pass ``None`` when
    the call comes from the Segment 18G scheduled-activation trigger
    (``actor_user_id`` on the audit event matches the
    ``observe_deadline`` convention). ``trigger`` flows into
    ``context.trigger`` on the ``session.activated`` audit event so
    operator-vs-scheduled provenance is visible in the log.

    On success the function also **clears**
    ``scheduled_activate_at`` in the same transaction — the Part 1
    "manual-activate consumes the schedule" / "scheduled-trigger
    consumes the schedule" rule. Either way, once the session is
    ``ready`` the schedule has done its job.
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
    # First-activation stamp (17B Phase 2 PR A). Lights up the
    # **Start** column on the reviewer lobby. Idempotent on
    # subsequent re-activations — the column records the
    # *first* time this session went live; later revert + re-
    # activate cycles don't overwrite it.
    if review_session.activated_at is None:
        review_session.activated_at = datetime.now(timezone.utc)
    # Consume the scheduled-activation column (Segment 18G Part 1).
    # Whether activation fired via the scheduled trigger or via a
    # manual click during the window, the schedule has done its job.
    review_session.scheduled_activate_at = None
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    for instrument in instruments:
        if (
            instrument.group_kind is not None
            and instrument.rule_set_id is None
            and not instrument.is_new_model
        ):
            # A legacy group-scoped instrument with no pinned rule
            # cannot accept responses (Segment 13C rule-required
            # gate); it stays closed until the operator pins a rule
            # and opens it. New-model group-scoped instruments
            # default to Full Matrix on untouched Band 1 (Wave 4)
            # so they don't need an explicit pin.
            continue
        instrument.accepting_responses = True
        instrument.deadline_closed_at = None
    db.flush()

    audit.write_event(
        db,
        event_type="session.activated",
        summary=f"Session {review_session.code} activated",
        actor_user_id=user.id if user is not None else None,
        session=review_session,
        payload=audit.counts(
            warnings=len(report.warnings),
            info=len(report.info),
            instruments=len(instruments),
        ),
        context={
            "prev_status": prev_status,
            "override_warnings": bool(report.has_non_blocking_findings),
            "trigger": trigger,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    log.info(
        "session activated",
        extra={
            "session_id": review_session.id,
            "code": review_session.code,
            "instruments": len(instruments),
            "override_warnings": bool(report.has_non_blocking_findings),
            "trigger": trigger,
            "correlation_id": correlation_id,
        },
    )
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


def archive_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip ``draft → archived`` — file a session out of the active lobby.

    Archiving is reversible (see ``unarchive_session``) and deletes no
    data. Only ``draft`` sessions are eligible: a running session is
    reverted to draft first. Raises ``LifecycleError`` otherwise.
    """
    if not is_draft(review_session):
        raise LifecycleError(
            f"Session is {review_session.status}, can only archive from draft",
            code="not_draft",
        )
    review_session.status = SessionStatus.archived.value
    db.flush()
    audit.write_event(
        db,
        event_type="session.archived",
        summary=f"Session {review_session.code} archived",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"status": ["draft", "archived"]}),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def unarchive_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip ``archived → draft`` — restore an archived session to the
    active lobby. Raises ``LifecycleError`` if not archived."""
    if review_session.status != SessionStatus.archived.value:
        raise LifecycleError(
            f"Session is {review_session.status}, can only unarchive from "
            "archived",
            code="not_archived",
        )
    review_session.status = SessionStatus.draft.value
    db.flush()
    audit.write_event(
        db,
        event_type="session.unarchived",
        summary=f"Session {review_session.code} unarchived",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"status": ["archived", "draft"]}),
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

    if (
        instrument.group_kind is not None
        and instrument.rule_set_id is None
        and not instrument.is_new_model
    ):
        # Legacy group-scoped instruments still require an explicit
        # pin; new-model group-scoped instruments default to Full
        # Matrix on untouched Band 1 (Wave 4).
        raise LifecycleError(
            "A group-scoped instrument needs an assignment rule before "
            "it can accept responses. Pin one on the Assignments page.",
            code="group_instrument_no_rule",
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


def session_status_for_reviewer(
    db: Session,
    *,
    reviewer: Reviewer,
    review_session: ReviewSession,
    now: datetime | None = None,
) -> str:
    """The reviewer-lobby **Session Status** label for one
    reviewer's view of one session — ``"not opened"`` /
    ``"open"`` / ``"closed"`` (Segment 17B Phase 2 PR A).

    A non-mutating peek at the session's state. Does not call
    :func:`observe_deadline`; the deadline check flows through
    :func:`session_accepts_responses` directly, so a past
    deadline reads as ``closed`` even on instruments whose
    ``accepting_responses=True`` flag hasn't been flipped yet.
    """
    if not is_ready(review_session):
        return "not opened"
    assignment_rows = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
            Assignment.include.is_(True),
        )
    ).scalars()
    instrument_ids = {a.instrument_id for a in assignment_rows}
    if not instrument_ids:
        # Reviewer has no active assignments on this session.
        # Treat as closed from their POV — there is nothing to
        # open.
        return "closed"
    instruments = db.execute(
        select(Instrument).where(Instrument.id.in_(instrument_ids))
    ).scalars()
    for instrument in instruments:
        if session_accepts_responses(review_session, instrument, now=now):
            return "open"
    return "closed"


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


def needs_regeneration_after_revert(db: Session, session_id: int) -> bool:
    """True iff the session's most recent ``session.invalidated`` or
    ``session.reverted_to_draft`` audit event is newer than its most
    recent ``assignments.generated`` event. Surfaces the post-revert
    case where assignment rows still exist from before the revert but
    the operator hasn't regenerated since — drives the Next Action
    card's State 1A on a reverted session."""
    revert_events = {"session.invalidated", "session.reverted_to_draft"}
    last_revert = db.scalar(
        select(AuditEvent.id)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type.in_(revert_events))
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    if last_revert is None:
        return False
    last_generate = db.scalar(
        select(AuditEvent.id)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type == "assignments.generated")
        .order_by(AuditEvent.id.desc())
        .limit(1)
    )
    return last_generate is None or last_revert > last_generate


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
    "archive_session",
    "unarchive_session",
    "open_instrument",
    "close_instrument",
    "set_responses_visible_when_closed",
    "session_accepts_responses",
    "observe_deadline",
    "session_has_responses",
    "assert_status_draft",
]
