from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.schemas.sessions import SessionCreate
from app.services import audit, operator_settings, session_lifecycle as lifecycle
from app.services.instruments import ensure_default_instrument
from app.services.library_materialise import materialise_operator_libraries
from app.services.rules.seeds import materialise_seed_rule_sets


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
        created_by_user_id=user.id,
        # 18B PR 3: stamp the creating operator's default display
        # timezone at create time. A snapshot, not a live link —
        # changing the operator default later leaves this untouched.
        display_timezone=operator_settings.get_display_timezone(user),
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

    # 15C Slice 1: copy workspace-shipped seed RuleSets into the
    # session's ``session_rule_sets`` pool. The 15B per-instrument
    # picker (and the Rule Builder, post-15C Slice 4) read from
    # this pool.
    seed_rows = materialise_seed_rule_sets(db, review_session)

    # 15C Slice 2: auto-copy the operator's library (RTDs + Personal
    # RuleSets) into the per-session tables. Seeds-first order means
    # any (rare) name collision goes to the seed; library entries
    # with colliding names are skipped silently.
    library_result = materialise_operator_libraries(
        db, review_session, owner_user=user
    )

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
    if seed_rows:
        audit.write_event(
            db,
            event_type="session_rule_sets.materialised_from_seed",
            summary=(
                f"Materialised {len(seed_rows)} seeded RuleSet(s) "
                f"into session {review_session.code}"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.counts(
                materialised=len(seed_rows),
            ),
            correlation_id=correlation_id,
        )
    if library_result.rtds_copied:
        audit.write_event(
            db,
            event_type="response_type_definitions.materialised_from_library",
            summary=(
                f"Copied {library_result.rtds_copied} library RTD(s) "
                f"into session {review_session.code}"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.counts(
                materialised=library_result.rtds_copied,
            ),
            correlation_id=correlation_id,
        )
    if library_result.rule_sets_copied:
        audit.write_event(
            db,
            event_type="session_rule_sets.materialised_from_library",
            summary=(
                f"Copied {library_result.rule_sets_copied} library "
                f"RuleSet(s) into session {review_session.code}"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.counts(
                materialised=library_result.rule_sets_copied,
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
    for field_name in ("name", "code", "description", "deadline", "help_contact"):
        old = getattr(review_session, field_name)
        new = getattr(payload, field_name)
        if old != new:
            diffs[field_name] = [old, new]
            setattr(review_session, field_name, new)
    db.flush()

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
