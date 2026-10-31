from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.services import participants


def user_can_view_session(db: Session, user: User, session_id: int) -> bool:
    stmt = select(SessionOperator.id).where(
        SessionOperator.session_id == session_id,
        SessionOperator.user_id == user.id,
    )
    return db.execute(stmt).first() is not None


def may_name_session(
    db: Session, user: User | None, review_session: ReviewSession
) -> bool:
    """Whether ``user`` may be told this session's name: a sys-admin
    (Sessions Diagnostics lists every session by name), one of its
    operators, or a participant whose role on it may be disclosed to
    them (``participants.disclosable_roles``, so a reviewee only while a
    grant resolves). Grants nothing; it answers what a label may say
    (``app/web/return_to.py``)."""
    if user is None:
        return False
    if user.is_sys_admin:
        return True
    if user_can_view_session(db, user, review_session.id):
        return True
    return bool(
        participants.disclosable_roles(
            db,
            user.email,
            principal_id=getattr(user, "signed_in_principal_id", None),
            session_id=review_session.id,
        )
    )
