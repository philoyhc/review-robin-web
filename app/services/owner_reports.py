"""Report emails to a session's other owners (14C Item 4).

When an owner acts on a session, each *other* owner who turned that
report on is mailed from the acting owner's mailbox (mail goes as the
operator who acts, ruling 2026-11-02; group B, author's ruling
2026-11-06). Three groups of actions, one preference each:

- lifecycle: activated, reverted to draft, archived, unarchived, deleted;
- destructive: responses or rosters purged, all responses or a roster
  deleted;
- owners: an owner added or removed, responses released or stopped.

**How a report travels.** ``audit.write_event`` calls :func:`note` for
each event type in :data:`REPORTED`. The recipients are decided there,
inside the action's transaction, while the owners can still be read.
Nothing is mailed yet: a note waits on the database session until its
transaction **commits** (a rollback drops it), and the request's
:func:`send_ready` mails what committed after the route has answered.
A failure is recorded (``report.send_failed``) and the action stands.

Rejected: mailing from the audit write itself, before the commit, and a
call from each of the dozen routes that reach these actions, which the
lobby's bulk forms and the Workflow card would make easy to miss.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import event, select
from sqlalchemy.orm import Session, SessionTransaction

from app.db.models import ReviewSession, SessionOperator, User

log = logging.getLogger("app.services.owner_reports")

#: Event type → (the recipient's preference key, the line the report says).
REPORTED: Mapping[str, tuple[str, str]] = {
    "session.activated": ("email_report_lifecycle", "activated"),
    "session.reverted_to_draft": ("email_report_lifecycle", "reverted to draft"),
    "session.archived": ("email_report_lifecycle", "archived"),
    "session.unarchived": ("email_report_lifecycle", "unarchived"),
    "session.deleted": ("email_report_lifecycle", "deleted"),
    "session.responses_purged": ("email_report_destructive", "purged the responses of"),
    "session.rosters_purged": ("email_report_destructive", "purged the rosters of"),
    "responses.deleted_all": ("email_report_destructive", "deleted all responses in"),
    "reviewers.deleted_all": ("email_report_destructive", "deleted the Reviewers roster of"),
    "reviewees.deleted_all": ("email_report_destructive", "deleted the Reviewees roster of"),
    "observers.deleted_all": ("email_report_destructive", "deleted the Observers roster of"),
    "relationships.deleted_all": ("email_report_destructive", "deleted the Relationships of"),
    "session.owner_added": ("email_report_owners", "added {target} as an owner of"),
    "session.owner_removed": ("email_report_owners", "removed {target} as an owner of"),
    "session.responses_released": ("email_report_owners", "released the responses of"),
    "session.responses_release_stopped": ("email_report_owners", "stopped the release of"),
}

_PENDING = "owner_reports_pending"
_READY = "owner_reports_ready"
_DOOMED = "owner_reports_doomed_owners"


@dataclass(frozen=True)
class Report:
    """One email to one owner about one action."""

    to: str
    actor_user_id: int
    actor_name: str
    session_id: int | None
    session_public_id: str | None
    session_code: str
    session_name: str
    what: str
    when: str
    event_type: str


def _owners(db: Session, session_id: int) -> list[User]:
    return list(
        db.execute(
            select(User)
            .join(SessionOperator, SessionOperator.user_id == User.id)
            .where(SessionOperator.session_id == session_id)
        ).scalars()
    )


def before_delete(db: Session, review_session: ReviewSession) -> None:
    """Keep ``review_session``'s owners and time zone for its
    ``session.deleted`` note: by the time that event is written, they are
    gone with the session."""
    from app.services.sessions import resolve_session_timezone

    doomed = cast(dict[int, tuple[list[User], str]], db.info.setdefault(_DOOMED, {}))
    doomed[review_session.id] = (
        _owners(db, review_session.id),
        resolve_session_timezone(review_session),
    )


def _wants(user: User, key: str) -> bool:
    return (user.preferences or {}).get(key) is True


def note(
    db: Session,
    *,
    event_type: str,
    actor_user_id: int | None,
    review_session: ReviewSession | None,
    snapshot: Mapping[str, Any] | None = None,
    target_user_id: int | None = None,
) -> None:
    """Queue the reports ``event_type`` owes, decided now. A no-op for an
    event no one is told of, with no actor (the clock's own actions are
    group C), or whose actor is not an owner of the session: group B is an
    *owner's* action, and a participant's (a reviewer's Clear all) is
    group D's, mailed from no participant's mailbox (cold read, 2026-11-06)."""
    reported = REPORTED.get(event_type)
    if reported is None or actor_user_id is None:
        return
    key, what = reported
    from app.services import date_formatting
    from app.services.sessions import resolve_session_timezone

    now = datetime.now(UTC)
    if review_session is not None:
        session_id: int | None = review_session.id
        public_id: str | None = review_session.public_id
        code, name = review_session.code, review_session.name
        owners = _owners(db, review_session.id)
        zone: str | None = resolve_session_timezone(review_session)
    else:  # session.deleted: the row is gone, its snapshot and owners kept
        snap = snapshot or {}
        raw_id = snap.get("id")
        session_id = raw_id if isinstance(raw_id, int) else None
        public_id = None  # nothing to link to
        code, name = str(snap.get("code", "")), str(snap.get("name", ""))
        doomed = cast(dict[int, tuple[list[User], str]], db.info.get(_DOOMED, {}))
        kept = doomed.pop(session_id, None) if session_id is not None else None
        # The session's zone, kept with its owners (Codex on #3694).
        owners, zone = kept if kept is not None else ([], None)
    target = db.get(User, target_user_id) if target_user_id is not None else None
    if all(o.id != actor_user_id for o in owners) and target_user_id != actor_user_id:
        return  # not an owner's action
    if target is not None:
        what = what.format(target=target.display_name or target.email)
        if all(o.id != target.id for o in owners):
            owners.append(target)  # an owner just removed is told
    # With its zone, so a report read in another zone is not misread.
    when = (
        f"{date_formatting.format_datetime(now, zone)} "
        f"({date_formatting.gmt_offset_zone_label(zone, at=now)})"
    )
    actor = db.get(User, actor_user_id)
    actor_name = (actor.display_name or actor.email) if actor is not None else "Another owner"
    pending = cast(list[Report], db.info.setdefault(_PENDING, []))
    for owner in owners:
        # not-identity: ids compared; the email is only tested for presence
        if owner.id == actor_user_id or not owner.email or not _wants(owner, key):
            continue
        pending.append(
            Report(
                to=owner.email,
                actor_user_id=actor_user_id,
                actor_name=actor_name,
                session_id=session_id,
                session_public_id=public_id,
                session_code=code,
                session_name=name,
                what=what,
                when=when,
                event_type=event_type,
            )
        )


@event.listens_for(Session, "after_commit")
def _promote(db: Session) -> None:
    # A savepoint's release fires this too, and the session lock opens one
    # on Postgres: only the outermost commit promotes (cold read).
    if db.in_nested_transaction():
        return
    pending = cast(list[Report], db.info.pop(_PENDING, []))
    if pending:
        cast(list[Report], db.info.setdefault(_READY, [])).extend(pending)


@event.listens_for(Session, "after_soft_rollback")
def _drop(db: Session, previous: SessionTransaction) -> None:
    # A savepoint's rollback leaves the outer transaction's notes standing.
    if previous.nested:
        return
    db.info.pop(_PENDING, None)
    db.info.pop(_DOOMED, None)


def take_ready(db: Session) -> list[Report]:
    """The committed reports not yet sent, removed from ``db``."""
    return cast(list[Report], db.info.pop(_READY, []))


def compose(report: Report, *, session_link: str | None) -> tuple[str, str]:
    """The subject and plain-text body of ``report``."""
    label = f"{report.session_name} ({report.session_code})"
    subject = f"Review Robin: {report.actor_name} {report.what} {label}"
    lines = [
        f"{report.actor_name} {report.what} the session {label}, {report.when}.",
        "",
        "You are told because you own this session, or did until this",
        "action, and asked to be: Settings, Email settings, Report emails.",
    ]
    if session_link:
        lines += ["", f"Session Home: {session_link}"]
    return subject, "\n".join(lines)


def send_ready(
    db: Session,
    reports: list[Report],
    *,
    send: Callable[[Report], None],
    correlation_id: str | None = None,
) -> None:
    """Mail ``reports`` through ``send`` and record each outcome. ``send``
    raises on a refusal; the error's ``kind``, when it has one, is
    recorded, never its message."""
    from app.services import audit

    # Whatever the route left uncommitted is not this function's to keep.
    db.rollback()
    for report in reports:
        review_session = (
            db.get(ReviewSession, report.session_id) if report.session_id is not None else None
        )
        try:
            send(report)
        except Exception as exc:  # recorded, never raised: the action stands
            kind = str(getattr(exc, "kind", type(exc).__name__))
            log.warning(
                "owner report not sent",
                extra={"event": "report.send_failed", "kind": kind},
            )
            audit.write_event(
                db,
                event_type="report.send_failed",
                summary=f"A report of {report.event_type} could not be sent",
                actor_user_id=report.actor_user_id,
                session=review_session,
                payload=audit.counts(recipients=1),
                reason=kind,
                context={"event": report.event_type, "session_code": report.session_code},
                correlation_id=correlation_id,
            )
            continue
        audit.write_event(
            db,
            event_type="report.sent",
            summary=f"Reported {report.event_type} to another owner",
            actor_user_id=report.actor_user_id,
            session=review_session,
            payload=audit.counts(recipients=1),
            context={"event": report.event_type, "session_code": report.session_code},
            correlation_id=correlation_id,
        )
    if reports:
        db.commit()
