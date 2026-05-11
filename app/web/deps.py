from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.config import settings as default_settings
from app.db.models import Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import permissions, sessions


class OperatorAllowlistDenied(Exception):
    """Raised by ``require_operator`` when a signed-in user is not on
    the workspace's operator / sys-admin allowlist (the Option C
    strict-allowlist gate; 16A PR 1).

    The exception handler registered in ``app/main.py`` converts this
    into a 303 redirect to ``/request-access`` — the deliberate UX
    choice over a raw 403 (gentler for the misrouted-but-legitimate
    arrival).
    """


def _email_in(allowlist: list[str], email: str | None) -> bool:
    if not email:
        return False
    target = email.casefold()
    return any(item.casefold() == target for item in allowlist)


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

    # Option C strict-allowlist bootstrap on first sign-in. Env vars
    # seed the persisted columns once; after that the columns are
    # authoritative. Removing an email from the env var does NOT
    # auto-revoke — revocation goes through 16A PR 6's workspace UI.
    # See ``guide/segment_16A_sys_admin_page.md`` F3.
    cfg = default_settings
    is_operator = _email_in(cfg.operator_emails, current_user.email)
    is_sys_admin = _email_in(cfg.sys_admin_emails, current_user.email)
    if cfg.allow_fake_auth and current_user.is_fake:
        if cfg.fake_auth_operator:
            is_operator = True
        if cfg.fake_auth_sys_admin:
            is_sys_admin = True

    user = User(
        email=current_user.email,
        display_name=current_user.name,
        external_principal_id=current_user.principal_id,
        is_operator=is_operator,
        is_sys_admin=is_sys_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def require_operator(user: User = Depends(get_or_create_user)) -> User:
    """16A PR 1 access gate. Passes when the user is on the workspace
    operator allowlist, OR is a sys-admin (sys-admin implies operator
    per F4). Anyone else is bounced to ``/request-access`` via the
    ``OperatorAllowlistDenied`` exception handler in ``app/main.py``.
    """
    if user.is_operator or user.is_sys_admin:
        return user
    raise OperatorAllowlistDenied()


def require_sys_admin(user: User = Depends(get_or_create_user)) -> User:
    """16A PR 2 access gate for the Sys Admin chrome and its
    sub-surfaces. Returns the user on hit; raises 403
    ``sys_admin required`` on miss. Layers on top of (and is
    strictly tighter than) ``require_operator``.
    """
    if user.is_sys_admin:
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="sys_admin required",
    )


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
