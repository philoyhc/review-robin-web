from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SessionOperator, User


def user_can_view_session(db: Session, user: User, session_id: int) -> bool:
    stmt = select(SessionOperator.id).where(
        SessionOperator.session_id == session_id,
        SessionOperator.user_id == user.id,
    )
    return db.execute(stmt).first() is not None
