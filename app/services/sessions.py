from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.schemas.sessions import SessionCreate
from app.services import audit, session_lifecycle as lifecycle
from app.services.instruments import ensure_default_instrument


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

    audit.write_event(
        db,
        event_type="session.created",
        summary=f"Session {review_session.code} created",
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={
            "session_id": review_session.id,
            "code": review_session.code,
            "name": review_session.name,
        },
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
    changes: dict[str, list[Any]] = {}
    for field in ("name", "code", "description", "deadline", "help_contact"):
        old = getattr(review_session, field)
        new = getattr(payload, field)
        if old != new:
            changes[field] = [old, new]
            setattr(review_session, field, new)
    db.flush()

    audit.write_event(
        db,
        event_type="session.updated",
        summary=(
            f"Session {review_session.code} updated"
            if changes
            else f"Session {review_session.code} edited (no changes)"
        ),
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={
            "session_id": review_session.id,
            "code": review_session.code,
            "changes": _serialise_changes(changes),
        },
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(review_session)
    return review_session


def _serialise_changes(changes: dict[str, list[Any]]) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for field, (old, new) in changes.items():
        out[field] = [_serialise(old), _serialise(new)]
    return out


def _serialise(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


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
    snapshot = {
        "session_id": review_session.id,
        "code": review_session.code,
        "name": review_session.name,
    }
    db.execute(delete(AuditEvent).where(AuditEvent.session_id == review_session.id))
    db.delete(review_session)
    db.flush()

    audit.write_event(
        db,
        event_type="session.deleted",
        summary=f"Deleted session {snapshot['code']}",
        actor_user_id=user.id,
        session_id=None,
        detail=snapshot,
        correlation_id=correlation_id,
    )
    db.commit()
