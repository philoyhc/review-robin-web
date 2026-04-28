from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.schemas.sessions import SessionCreate
from app.services import audit


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
