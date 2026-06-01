from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Observer,
    Relationship,
    ReviewSession,
    SessionOperator,
    User,
)
from app.logging_config import get_logger
from app.schemas.sessions import SessionCreate
from app.services import audit, operator_settings, session_lifecycle as lifecycle
from app.services.instruments import ensure_default_instrument
# Wave 5 PR 5.2 — RuleSet seeding retired; ``app.services.rules.seeds``
# module deleted entirely. New sessions land with no rows in
# ``session_rule_sets``. Band 1's inline editor lazily materialises
# rows when the operator authors rules.

log = get_logger(__name__)


def create_session(
    db: Session,
    *,
    user: User,
    payload: SessionCreate,
    correlation_id: str | None = None,
) -> ReviewSession:
    review_session = ReviewSession(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        deadline=payload.deadline,
        help_contact=payload.help_contact,
        # 18G Part 1: optional operator-set Start anchor. None ⇒ no
        # scheduled activation; route layer enforces the minimum
        # lead time on save.
        scheduled_activate_at=payload.scheduled_activate_at,
        # 18G Part 2: optional list of auto-send invitation offsets.
        # Route layer enforces per-entry rules (operational lead +
        # reviewer-notice gap) at save against the current Start.
        invite_offsets=payload.invite_offsets,
        # 18G Part 3: optional list of auto-send reminder offsets,
        # anchored on ``deadline``. Same per-entry rules apply at
        # save time against the deadline anchor.
        reminder_offsets=payload.reminder_offsets,
        # Participant-model Phase 2 — per-session feature toggles
        # mirrored from the User interface settings card on the
        # Create / Edit Session pages.
        relationships_enabled=payload.relationships_enabled,
        observers_enabled=payload.observers_enabled,
        # Participant-model Phase 3 (W14 + S12) — Release-responses
        # window anchor + absolute close datetime. Route layer
        # parses + validates; the §8.2.2 anchor-null rule handles
        # inertness at view time.
        responses_release_at=payload.responses_release_at,
        responses_release_until=payload.responses_release_until,
        created_by_user_id=user.id,
        # 18B PR 3 / PR 4: the per-session display timezone. The
        # Create Session form submits an explicit zone (defaulted to
        # the operator's default in the picker); callers that omit it
        # fall back to the operator default here. Either way it's a
        # snapshot — changing the operator default later leaves this
        # untouched.
        display_timezone=(
            payload.display_timezone
            or operator_settings.get_display_timezone(user)
        ),
    )
    db.add(review_session)
    db.flush()

    db.add(
        SessionOperator(
            session_id=review_session.id,
            user_id=user.id,
            role="owner",
        )
    )

    # Model invariant: every session has at least one Instrument with
    # response fields. The reviewer surface (Segment 8) renders against
    # these defaults; a future instrument-builder will let operators
    # rename / extend / replace them.
    ensure_default_instrument(db, review_session)

    # Wave 5 PR 5.2 — RuleSet seeding retired entirely. New
    # sessions land with no rows in ``session_rule_sets``;
    # Band 1's inline editor lazily materialises rows on first
    # save. New-model instruments default to Full Matrix via
    # the synthetic schema (Wave 4 PR 1) when no rule_set_id
    # is pinned.

    audit.write_event(
        db,
        event_type="session.created",
        summary=f"Session {review_session.code} created",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "id": review_session.id,
                "code": review_session.code,
                "name": review_session.name,
            }
        ),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def list_for_user(db: Session, user: User) -> list[ReviewSession]:
    stmt = (
        select(ReviewSession)
        .join(SessionOperator, SessionOperator.session_id == ReviewSession.id)
        .where(SessionOperator.user_id == user.id)
        .order_by(ReviewSession.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


def list_all(db: Session) -> list[ReviewSession]:
    """Workspace-wide session list, no per-user filter. Used by the
    Sys Admin Sessions Diagnostics table (16A PR 3); callers must
    gate on ``require_sys_admin`` before invoking — this helper
    does not enforce access control.
    """
    stmt = select(ReviewSession).order_by(ReviewSession.created_at.desc())
    return list(db.execute(stmt).scalars())


def get_for_user(db: Session, user: User, session_id: int) -> ReviewSession | None:
    stmt = (
        select(ReviewSession)
        .join(SessionOperator, SessionOperator.session_id == ReviewSession.id)
        .where(
            ReviewSession.id == session_id,
            SessionOperator.user_id == user.id,
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def update_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    payload: SessionCreate,
    correlation_id: str | None = None,
) -> ReviewSession:
    """Apply payload to ``review_session`` and record changed fields in audit."""
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="session_edited",
        correlation_id=correlation_id,
    )
    diffs: dict[str, list[object]] = {}
    for field_name in (
        "name",
        "code",
        "description",
        "deadline",
        "help_contact",
        "scheduled_activate_at",
        "invite_offsets",
        "reminder_offsets",
        "relationships_enabled",
        "observers_enabled",
        "responses_release_at",
        "responses_release_until",
    ):
        old = getattr(review_session, field_name)
        new = getattr(payload, field_name)
        if old != new:
            diffs[field_name] = [old, new]
            setattr(review_session, field_name, new)
    db.flush()

    # Lock-on-data — once a roster has rows, the corresponding
    # toggle cannot flip True→False (it would orphan the data).
    # The Edit Session UI renders the checkbox `disabled` in this
    # state, so the form simply omits the field; but a direct
    # API call could still attempt the flip. Silent no-op for
    # safety. See ``guide/archive/participant_model_upgrade.md`` §3.8
    # "Lock-on-data".
    if "relationships_enabled" in diffs:
        old, new = diffs["relationships_enabled"]
        if old is True and new is False and _has_relationships(
            db, review_session.id
        ):
            review_session.relationships_enabled = True
            del diffs["relationships_enabled"]
    # Observers symmetric — defensive even though the table ships
    # empty today; future operators may flip after populating.
    if "observers_enabled" in diffs:
        old, new = diffs["observers_enabled"]
        if old is True and new is False and _has_observers(
            db, review_session.id
        ):
            review_session.observers_enabled = True
            del diffs["observers_enabled"]
    db.flush()

    # 18G Part 1 — when scheduled_activate_at changes, also emit a
    # dedicated audit event so the UI can surface "operator just
    # scheduled / cleared an activation" without filtering generic
    # session.updated rows. The general session.updated still records
    # the change alongside other field edits in the same save.
    if "scheduled_activate_at" in diffs:
        audit.write_event(
            db,
            event_type="session.activation_scheduled",
            summary=f"Session {review_session.code} scheduled-activation updated",
            actor_user_id=user.id,
            session=review_session,
            payload=audit.changes(
                {"scheduled_activate_at": diffs["scheduled_activate_at"]}
            ),
            correlation_id=correlation_id,
        )
    # 18G Part 2 — same dedicated-event pattern for invite_offsets.
    if "invite_offsets" in diffs:
        audit.write_event(
            db,
            event_type="session.invite_schedule_updated",
            summary=f"Session {review_session.code} invite schedule updated",
            actor_user_id=user.id,
            session=review_session,
            payload=audit.changes(
                {"invite_offsets": diffs["invite_offsets"]}
            ),
            correlation_id=correlation_id,
        )
    # 18G Part 3 — same dedicated-event pattern for reminder_offsets.
    if "reminder_offsets" in diffs:
        audit.write_event(
            db,
            event_type="session.reminder_schedule_updated",
            summary=f"Session {review_session.code} reminder schedule updated",
            actor_user_id=user.id,
            session=review_session,
            payload=audit.changes(
                {"reminder_offsets": diffs["reminder_offsets"]}
            ),
            correlation_id=correlation_id,
        )
    # Participant-model §3.8 — dedicated event when either of the
    # per-session feature toggles flips. Carries only the toggle
    # changes; the general ``session.updated`` still records them
    # alongside other field edits in the same save.
    toggle_changes = {
        f: diffs[f]
        for f in ("relationships_enabled", "observers_enabled")
        if f in diffs
    }
    if toggle_changes:
        audit.write_event(
            db,
            event_type="session.feature_toggled",
            summary=(
                f"Session {review_session.code} feature toggle(s) updated"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.changes(toggle_changes),
            correlation_id=correlation_id,
        )

    audit.write_event(
        db,
        event_type="session.updated",
        summary=(
            f"Session {review_session.code} updated"
            if diffs
            else f"Session {review_session.code} edited (no changes)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes(diffs),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def resolve_session_timezone(review_session: ReviewSession) -> str:
    """The display zone for a session-scoped render (Segment 18B PR 3).

    Resolution order: the session's own ``display_timezone`` override
    → the creating operator's default → ``UTC``. ``get_display_timezone``
    supplies the ``UTC`` floor, so this never returns an empty string.
    """
    override = review_session.display_timezone
    if override and operator_settings.is_valid_timezone(override):
        return override
    return operator_settings.get_display_timezone(
        review_session.created_by_user
    )


def set_session_display_timezone(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    timezone_name: str | None,
    correlation_id: str | None = None,
) -> None:
    """Persist a session's display-timezone override (Segment 18B PR 3).

    ``timezone_name=None`` clears the override — the session falls back
    to inheriting the creating operator's default. A no-op when the
    value is unchanged. Raises ``ValueError`` for an unknown zone.
    """
    if timezone_name is not None and not operator_settings.is_valid_timezone(
        timezone_name
    ):
        raise ValueError(f"unknown timezone {timezone_name!r}")

    old = review_session.display_timezone
    if old == timezone_name:
        return

    review_session.display_timezone = timezone_name
    db.flush()

    audit.write_event(
        db,
        event_type="session.display_timezone_set",
        summary=(
            f"Session {review_session.code} display timezone set to "
            f"{timezone_name or 'inherit operator default'}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"display_timezone": [old, timezone_name]}),
        correlation_id=correlation_id,
    )
    db.commit()


def delete_session(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> None:
    """Delete a session and all its dependent rows.

    Audit events tied to this session are removed too. A new
    ``session.deleted`` event is then written with ``session_id=None``
    so the deletion itself stays in the global audit log.
    """
    captured = {
        "id": review_session.id,
        "code": review_session.code,
        "name": review_session.name,
    }
    db.execute(delete(AuditEvent).where(AuditEvent.session_id == review_session.id))
    db.delete(review_session)
    db.flush()

    audit.write_event(
        db,
        event_type="session.deleted",
        summary=f"Deleted session {captured['code']}",
        actor_user_id=user.id,
        session=None,
        payload=audit.snapshot(captured),
        correlation_id=correlation_id,
    )
    db.commit()
    log.info(
        "session deleted",
        extra={
            "session_id": captured["id"],
            "code": captured["code"],
            "correlation_id": correlation_id,
        },
    )



def _has_relationships(db: Session, session_id: int) -> bool:
    """True iff any ``relationships`` row exists for the session.

    Drives the lock-on-data check in ``update_session`` for the
    ``relationships_enabled`` toggle — once data is configured,
    the operator cannot flip the toggle off (it would orphan the
    data) without first deleting the rows.
    """
    return db.execute(
        select(Relationship.id)
        .where(Relationship.session_id == session_id)
        .limit(1)
    ).scalar_one_or_none() is not None


def _has_observers(db: Session, session_id: int) -> bool:
    """True iff any ``observers`` row exists for the session.

    Symmetric helper to ``_has_relationships`` for the
    ``observers_enabled`` toggle.
    """
    return db.execute(
        select(Observer.id)
        .where(Observer.session_id == session_id)
        .limit(1)
    ).scalar_one_or_none() is not None
