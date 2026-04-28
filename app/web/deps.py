from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.models import Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import permissions, sessions


def get_or_create_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated identity has no email claim",
        )

    user = db.execute(
        select(User).where(User.email == current_user.email)
    ).scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=current_user.email,
        display_name=current_user.name,
        external_principal_id=current_user.principal_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def require_session_operator(
    session_id: int,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> ReviewSession:
    if not permissions.user_can_view_session(db, user, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )
    review_session = sessions.get_for_user(db, user, session_id)
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return review_session


def require_reviewer_in_session(
    session_id: int,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> tuple[Reviewer, ReviewSession]:
    """403 unless the authenticated user has an active Reviewer row in the session.

    Identity match is case-insensitive email equality (``casefold()`` both
    sides). Reviewer rows whose ``status`` is anything other than ``active``
    do not grant access.
    """
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == session_id,
            Reviewer.status == "active",
        )
    ).scalars()
    user_email = (user.email or "").casefold()
    matched: Reviewer | None = None
    for r in reviewer:
        if r.email.casefold() == user_email:
            matched = r
            break
    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active reviewer in this session",
        )
    return matched, review_session


def request_correlation_id() -> str:
    return uuid.uuid4().hex
