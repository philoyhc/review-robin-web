"""Session lifecycle: status enum, readiness, activation, revert, instrument gates.

The operator-controlled lifecycle that gates reviewer write access. The
canonical session status values live here as a Python enum (no DB CHECK
constraint); all five are written (``spec/lifecycle.md``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Response,
    Reviewer,
    ReviewSession,
    User,
)
from app.logging_config import get_logger
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit
from app.services import unit_of_work
from app.services import session_guard
from app.services.session_guard import (  # noqa: F401 — re-exported
    LifecycleError,
    SessionStateConflict,
)

log = get_logger(__name__)


class SessionStatus(str, Enum):
    """Canonical session lifecycle values.

    9.5A adds ``validated`` between ``draft`` and ``ready``. All five
    values are live: :func:`expire_session` and :func:`archive_session`
    write ``expired`` and ``archived`` respectively. The enum constrains
    the string column at the application layer.

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
    expired = "expired"
    archived = "archived"


def is_ready(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.ready.value


def is_draft(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.draft.value


def is_validated(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.validated.value


def is_expired(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.expired.value


def is_archived(review_session: ReviewSession) -> bool:
    return review_session.status == SessionStatus.archived.value


def can_archive(review_session: ReviewSession) -> bool:
    """Archivable = any **non-activated**, non-archived session (draft /
    validated / expired). An activated (``ready``) session must be paused
    first; an already-archived one is a no-op. Shared gate for the lobby
    "Purge and archive" and the Extract data page's Archive card (18R —
    archive harmonization)."""
    return not is_ready(review_session) and not is_archived(review_session)


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalise a stored datetime to UTC-aware. SQLite's
    ``DateTime(timezone=True)`` column round-trips can read
    back naive in some refresh paths; the predicates below want
    a comparable tz-aware value. Naive values are assumed UTC
    (matches the project's "store everything in UTC" convention)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_response_release_window_open(
    review_session: ReviewSession, *, now: datetime | None = None
) -> bool:
    """Predicate for the after-release visibility window.

    Returns True when the operator-set release window is currently
    open — ``responses_release_at`` is set and reached, and either
    ``responses_release_until`` is NULL (open-ended) or hasn't yet
    arrived. Mirrors the predicate spelled out in
    ``spec/visibility_policy.md`` §3.2 and the resolver predicate
    in ``guide/archive/participant_model_upgrade.md`` §3.3.

    Anchor-null inertness: a saved ``responses_release_until``
    with no anchor reads as "not open yet" — the release-window
    doesn't open until the operator sets the anchor.

    **The session must be ``expired``** (Segment 19F PR 2a, author
    2026-09-07). The two visibility windows mean literally "as data is
    coming in" (``while_ongoing`` = ``ready``) and "after the review has
    closed" (``after_release`` = ``expired``); responses are released
    *because the session is over*. That was already the Workflow card's
    rule — it gates both Release and Stop-release on ``is_expired`` and
    says so in a comment — but the predicate itself checked only the
    anchors, so every path that sets them without the button opened the
    window in a state the UI would never offer:

    * an anchor **backdated** on Session Edit or Quick Setup, where
      ``parse_and_validate_responses_release_at`` deliberately applies no
      lead-time floor, opened the window on a ``draft`` session; and
    * ``revert_session_to_draft`` (``expired`` → ``draft``) does **not**
      clear the anchor, so a session the operator withdrew kept showing
      released responses to every non-operator audience.

    The second is the one that motivated the change: an operator who
    reverts to draft believes the session has been withdrawn, back to
    before activation. The anchor is left in place and simply goes inert
    — re-closing the session re-opens the window on the schedule they
    originally set, which is what "release at time T" should mean.
    """
    if not is_expired(review_session):
        return False
    anchor = _as_utc(review_session.responses_release_at)
    if anchor is None:
        return False
    if now is None:
        now = datetime.now(timezone.utc)
    if now < anchor:
        return False
    close = _as_utc(review_session.responses_release_until)
    if close is not None and now >= close:
        return False
    return True


def is_editable(review_session: ReviewSession) -> bool:
    """True when setup-mutating routes are allowed (``draft`` or ``validated``)."""
    return is_draft(review_session) or is_validated(review_session)


def require_editable(db: Session, review_session: ReviewSession) -> ReviewSession:
    """Lock + re-read the session, refuse unless :func:`is_editable`.

    The setup services' gate (findings Bc4): decided on the committed
    status, so a save cannot land on a session that went ``ready``
    after the request loaded it."""
    return session_guard.require_state(
        db,
        review_session,
        is_editable,
        code="not_editable",
        message="Session is {status}; revert to draft to edit",
    )


def require_not_archived(
    db: Session, review_session: ReviewSession
) -> ReviewSession:
    """Lock + re-read, refuse an ``archived`` session — the Observers
    roster's gate, which stays open while the session runs."""
    return session_guard.require_state(
        db,
        review_session,
        lambda locked: not is_archived(locked),
        code="archived",
        message="Session is archived; observer edits are not allowed.",
    )


def require_not_ready(
    db: Session, review_session: ReviewSession
) -> ReviewSession:
    """Lock + re-read, refuse a ``ready`` session — Session Home's
    Delete Data and Delete session gate (rulings C7 = G7)."""
    return session_guard.require_state(
        db,
        review_session,
        lambda locked: not is_ready(locked),
        code="session_ready",
        message="Session is {status}; revert to draft first to delete.",
    )


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
    session_guard.lock_session(db, review_session)
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

    Takes no lock of its own: the services that call it lock and re-read
    the session first, through ``require_editable`` (findings Bc4), so
    the status read here is the committed one.
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
    unit_of_work.commit(db)
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

    Requires the session to be in ``validated``. Raises ``LifecycleError``
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
    session_guard.lock_session(db, review_session)
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
        # Wave 5 PR 5.3 — every instrument flips to accepting on
        # activate. Untouched Band 1 (no pinned rule) is fine; the
        # synthetic Full Matrix schema (Wave 4 PR 1) covers it at
        # generate time.
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


def expire_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Flip ``ready → expired`` and close every instrument.

    The operator's "Close session" button on the Workflow card.
    Responses are preserved (drafts + submitted); whether reviewers
    can still read them is the visibility policy's call
    (``visibility_policies.reviewer_sees_own_responses``). From ``expired`` the
    operator can Revert to draft (see :func:`revert_session_to_draft`)
    to reopen the session for editing.
    """
    session_guard.lock_session(db, review_session)
    if not is_ready(review_session):
        raise LifecycleError(
            f"Session is {review_session.status}, can only expire from ready",
            code="not_ready",
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
    review_session.status = SessionStatus.expired.value
    db.flush()

    audit.write_event(
        db,
        event_type="session.expired",
        summary=f"Session {review_session.code} closed (expired)",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            closed_instruments=len(closed_instrument_ids),
        ),
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
    """Flip ready→draft (or expired→draft), close all instruments,
    preserve responses.

    Accepts both ``ready`` and ``expired`` as the starting state:
    from ``ready`` it's the live "Revert to draft" action mid-
    session; from ``expired`` it's the recovery path after the
    operator closed the session and wants to reopen it for
    editing. Both transitions preserve every ``Response`` row
    (drafts + submitted) so the operator's choice of "close
    session" / "revert" never destroys reviewer work — only
    Generate's reconcile drop ever does.
    """
    session_guard.lock_session(db, review_session)
    if not (is_ready(review_session) or is_expired(review_session)):
        raise LifecycleError(
            f"Session is {review_session.status}, can only revert from ready or expired",
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


def release_responses_now(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Force the response-release window open by stamping
    ``responses_release_at = now()`` and clearing any prior
    ``responses_release_until`` close-stamp.

    The "Release responses" button on the Workflow card calls
    this. It's a manual override on the schedule the operator
    set during edit — useful when an operator wants to publish
    results ahead of the scheduled release time, or when they
    previously stopped a release and want to re-open it.

    Emits ``session.responses_released`` with a snapshot of the
    new ``responses_release_at`` + a ``cleared_until`` flag when
    the prior close-stamp was non-null. The session lifecycle
    state isn't changed by this call.

    **They are no longer orthogonal, though** (19F PR 2a): the
    window this stamps only *opens* while the session is
    ``expired``, so stamping an anchor on a ``ready`` session
    grants nobody anything. The Workflow card only offers the
    button on an expired session, which is why the anchor and the
    state agreed before the predicate enforced it.
    """
    session_guard.require_state(
        db,
        review_session,
        lambda locked: not is_archived(locked),
        code="archived",
        message="Archived sessions can't have responses released.",
    )
    now = datetime.now(timezone.utc)
    cleared_until = review_session.responses_release_until is not None
    review_session.responses_release_at = now
    review_session.responses_release_until = None
    db.flush()
    audit.write_event(
        db,
        event_type="session.responses_released",
        summary=(
            f"Session {review_session.code} responses released "
            f"({now.isoformat()})"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "responses_release_at": now.isoformat(),
                "cleared_until": cleared_until,
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def stop_responses_release(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Close the response-release window by stamping
    ``responses_release_until = now()``.

    The "Stop releasing" button on the Workflow card
    calls this. Mirrors the release flow: the operator picks
    the close moment manually, overriding any scheduled
    ``responses_release_until``. Idempotent — a session whose
    window is already closed gets a fresh stamp on the close
    column but the audit log records each press.

    Emits ``session.responses_release_stopped`` with the new
    close-stamp.
    """
    session_guard.require_state(
        db,
        review_session,
        lambda locked: not is_archived(locked),
        code="archived",
        message="Archived sessions can't have releases stopped.",
    )
    now = datetime.now(timezone.utc)
    review_session.responses_release_until = now
    db.flush()
    audit.write_event(
        db,
        event_type="session.responses_release_stopped",
        summary=(
            f"Session {review_session.code} response release "
            f"stopped ({now.isoformat()})"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {"responses_release_until": now.isoformat()}
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
    """Flip any non-archived session into ``archived`` — file it
    out of the active lobby.

    Archiving is reversible (see ``unarchive_session``) and
    deletes no data. Accepts any starting state except
    ``archived`` itself; the audit event records the actual
    from-state so the round-trip is reconstructible. The lobby's
    "Purge and archive" and the Extract data page's Archive card
    reach it through ``session_purge.purge_and_archive``, which
    first refuses any session ``can_archive`` rejects; the
    workflow card's "Archive session" route calls it directly.
    """
    session_guard.lock_session(db, review_session)
    if is_archived(review_session):
        raise LifecycleError(
            f"Session is already {review_session.status}",
            code="already_archived",
        )
    from_status = review_session.status
    review_session.status = SessionStatus.archived.value
    db.flush()
    audit.write_event(
        db,
        event_type="session.archived",
        summary=f"Session {review_session.code} archived",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes(
            {"status": [from_status, SessionStatus.archived.value]}
        ),
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
    session_guard.lock_session(db, review_session)
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
# Accepting is session-wide, so there is no per-instrument open or close:
# ``activate_session`` opens every instrument, and ``observe_deadline``,
# Close session (``expire_session``) and Revert close them all. ``open_instrument`` / ``close_instrument``
# were removed with their routes on 2026-10-01.


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

    The post-Close-session ``expired`` state reports as
    ``"closed"`` (not ``"not opened"``) so the reviewer
    dashboard keeps the link to the session live — without that,
    reviewers couldn't reach ``/summary`` or the read-only surface
    after the operator closed the session.

    State → return value mapping:

    =================  =================================
    Lifecycle state    Returns
    =================  =================================
    ``draft``          ``"not opened"``
    ``validated``      ``"not opened"``
    ``archived``       ``"not opened"`` (by design — archive
                       retires a session out of reviewer reach;
                       the dashboard hides its link)
    ``expired``        ``"closed"``
    ``ready``          ``"open"`` if any instrument is
                       accepting + before deadline + the
                       reviewer has ≥1 active assignment,
                       else ``"closed"``
    =================  =================================
    """
    if is_expired(review_session):
        return "closed"
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


def _reopen_while_live(
    db: Session,
    review_session: ReviewSession,
    *,
    correlation_id: str | None,
) -> None:
    """Reopen any instrument a live session left closed.

    Only for a ``ready`` session before its deadline (the caller checks
    the deadline): every other state either has no accepting at all or
    closes it session-wide. Emits ``instrument.opened`` with
    ``reason="session_wide"`` per instrument reopened, so the heal is on
    the audit log. A no-op once no session carries a split.
    """
    if not is_ready(review_session):
        return

    def _closed(*, fresh: bool = False) -> list[Instrument]:
        query = select(Instrument).where(
            Instrument.session_id == review_session.id,
            Instrument.accepting_responses.is_(False),
        )
        if fresh:
            # After the lock (which flushed first): re-read rows loaded
            # earlier, which may be stale.
            query = query.execution_options(populate_existing=True)
        return list(db.execute(query).scalars())

    if not _closed():
        return
    # Something to heal: lock and decide again, so a Close session that
    # committed since this request loaded the row is not undone
    # (findings Bc4). Unlocked until then: this runs on every reviewer
    # request and almost always has nothing to do.
    session_guard.lock_session(db, review_session)
    if not is_ready(review_session):
        return
    closed = _closed(fresh=True)
    for instrument in closed:
        instrument.accepting_responses = True
        instrument.deadline_closed_at = None
        audit.write_event(
            db,
            event_type="instrument.opened",
            summary=(
                f"Instrument {instrument.name} reopened (accepting is "
                "session-wide)"
            ),
            actor_user_id=None,
            session=review_session,
            refs={"instrument_id": instrument.id},
            reason="session_wide",
            correlation_id=correlation_id,
        )
    db.flush()
    db.commit()


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

    **Before the deadline it heals the other way.** Accepting is
    session-wide, so a ``ready`` session before its deadline has every
    instrument open. One left closed by the retired per-instrument Close
    would otherwise block every reviewer write with no control to reopen
    it, so it is reopened here, on the same requests that would have hit
    the gate (see :func:`_reopen_while_live`).
    """
    current = now or datetime.now(timezone.utc)
    if review_session.deadline is None or current < _aware(
        review_session.deadline
    ):
        _reopen_while_live(db, review_session, correlation_id=correlation_id)
        return 0

    def _open(*, fresh: bool = False) -> list[Instrument]:
        query = select(Instrument).where(
            Instrument.session_id == review_session.id,
            Instrument.accepting_responses.is_(True),
            Instrument.deadline_closed_at.is_(None),
        )
        if fresh:
            # After the lock (which flushed first): re-read rows loaded
            # earlier, which may be stale.
            query = query.execution_options(populate_existing=True)
        return list(db.execute(query).scalars())

    if not _open():
        return 0
    # Lock and decide again before closing, so two requests tripping the
    # same deadline close each instrument (and audit it) once, and an End
    # cleared or moved later since this request loaded the row closes
    # nothing (findings Bc4). The async reviewer writes reach this through
    # the threadpool (their gate and their error re-render), so the wait
    # for a held lock stalls only this request.
    session_guard.lock_session(db, review_session)
    if review_session.deadline is None or current < _aware(
        review_session.deadline
    ):
        return 0
    instruments = _open(fresh=True)
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


def session_response_count(db: Session, review_session: ReviewSession) -> int:
    """How many ``Response`` rows sit under this session's assignments.

    ``session_has_responses`` answers the yes/no a gate needs;
    ``delete-all`` also has to *say* what it will destroy, and a count
    is what makes that sentence true rather than categorical
    (Segment 19I Item 3).
    """
    return int(
        db.execute(
            select(func.count())
            .select_from(Response)
            .join(Assignment, Assignment.id == Response.assignment_id)
            .where(Assignment.session_id == review_session.id)
        ).scalar_one()
    )


__all__ = [
    "SessionStatus",
    "ReadinessReport",
    "LifecycleError",
    "is_draft",
    "is_ready",
    "is_validated",
    "is_expired",
    "is_archived",
    "can_archive",
    "is_editable",
    "build_readiness_report",
    "mark_validated",
    "invalidate_if_validated",
    "invalidate_session",
    "activate_session",
    "expire_session",
    "revert_session_to_draft",
    "archive_session",
    "release_responses_now",
    "stop_responses_release",
    "unarchive_session",
    "session_accepts_responses",
    "observe_deadline",
    "session_has_responses",
    "session_response_count",
]
