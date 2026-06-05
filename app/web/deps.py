from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.config import settings as default_settings
from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.logging_config import get_logger
from app.services import operator_settings, participants, permissions, sessions

log = get_logger(__name__)


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


def _stash_display_timezone(request: Request, user: User) -> None:
    """Resolve the signed-in operator's default display timezone and
    park it on ``request.state`` for the Jinja context processor
    (``app/web/date_filters.py``) to pick up. Segment 18B PR 2."""
    request.state.display_timezone = operator_settings.get_display_timezone(
        user
    )


def get_or_create_user(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if not current_user.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated identity has no email claim",
        )

    # Case-insensitive lookup so a pre-seeded row (e.g. via the
    # sys-admin invite path at app/services/users.py:430) is reused
    # regardless of casing. Order by id and take the oldest match so
    # any historical case-variant duplicates (rows created before
    # this normalization landed) resolve deterministically to the
    # original row rather than raising MultipleResultsFound. The
    # storage-level guard against new duplicates is Slice D.
    user = db.execute(
        select(User)
        .where(func.lower(User.email) == current_user.email.lower())
        .order_by(User.id)
        .limit(1)
    ).scalar_one_or_none()
    if user is not None:
        _stash_display_timezone(request, user)
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
    _stash_display_timezone(request, user)
    return user


def require_operator(user: User = Depends(get_or_create_user)) -> User:
    """16A PR 1 access gate. Passes when the user is on the workspace
    operator allowlist, OR is a sys-admin (sys-admin implies operator
    per F4). Anyone else is bounced to ``/request-access`` via the
    ``OperatorAllowlistDenied`` exception handler in ``app/main.py``.
    """
    if user.is_operator or user.is_sys_admin:
        return user
    log.warning(
        "permission denied",
        extra={"gate": "require_operator", "user_id": user.id},
    )
    raise OperatorAllowlistDenied()


def require_sys_admin(user: User = Depends(get_or_create_user)) -> User:
    """16A PR 2 access gate for the Sys Admin chrome and its
    sub-surfaces. Returns the user on hit; raises 403
    ``sys_admin required`` on miss. Layers on top of (and is
    strictly tighter than) ``require_operator``.
    """
    if user.is_sys_admin:
        return user
    log.warning(
        "permission denied",
        extra={"gate": "require_sys_admin", "user_id": user.id},
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="sys_admin required",
    )


def _stash_session_timezone(
    request: Request, review_session: ReviewSession
) -> None:
    """Re-stamp ``request.state.display_timezone`` with the session's
    resolved zone, overriding the viewing-operator default that
    ``get_or_create_user`` parked there. Every session-scoped render
    then localises to the session zone. Segment 18B PR 3."""
    request.state.display_timezone = sessions.resolve_session_timezone(
        review_session
    )


def require_session_operator(
    session_id: int,
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> ReviewSession:
    if not permissions.user_can_view_session(db, user, session_id):
        log.warning(
            "permission denied",
            extra={
                "gate": "require_session_operator",
                "user_id": user.id,
                "session_id": session_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this session",
        )
    review_session = sessions.get_for_user(db, user, session_id)
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _stash_session_timezone(request, review_session)
    return review_session


def require_sys_admin_or_session_operator(
    session_id: int,
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> ReviewSession:
    """16A PR 3 relaxation. Used on the per-session diagnostic
    routes (Outbox, audit-log CSV) so a sys-admin reaching them from
    the workspace Admin chrome doesn't also need to be a
    ``session_operators`` member. Sys-admins bypass the membership
    check; everyone else falls through to the standard
    ``require_session_operator`` path.
    """
    if user.is_sys_admin:
        review_session = db.execute(
            select(ReviewSession).where(ReviewSession.id == session_id)
        ).scalar_one_or_none()
        if review_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        _stash_session_timezone(request, review_session)
        return review_session
    return require_session_operator(
        session_id=session_id, request=request, user=user, db=db
    )


def require_reviewer_in_session(
    session_id: int,
    request: Request,
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
        log.warning(
            "permission denied",
            extra={
                "gate": "require_reviewer_in_session",
                "user_id": user.id,
                "session_id": session_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active reviewer in this session",
        )
    _stash_session_timezone(request, review_session)
    return matched, review_session


def require_reviewee_in_session(
    session_id: int,
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> tuple[Reviewee, ReviewSession]:
    """403 unless the authenticated user has an active Reviewee row
    in the session whose ``email_or_identifier`` parses as an email
    matching the user's email (case-insensitive).

    Confidential reviewees — those whose identifier is not a valid
    email — never grant access; the surface stays unavailable by
    construction (``guide/archive/participant_model_upgrade.md`` §3.2).
    Reviewee rows whose ``status`` is anything other than ``active``
    do not grant access.

    Phase 1 stub — defined but not referenced by any route yet. The
    reviewee results surface (Phase 3 W16) wires this in as its
    auth gate.
    """
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user_email = (user.email or "").casefold()
    candidates = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == session_id,
            Reviewee.status == "active",
        )
    ).scalars()
    matched: Reviewee | None = None
    for r in candidates:
        if not participants.is_email_identified(r):
            continue
        if r.email_or_identifier.casefold() == user_email:
            matched = r
            break
    if matched is None:
        log.warning(
            "permission denied",
            extra={
                "gate": "require_reviewee_in_session",
                "user_id": user.id,
                "session_id": session_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active reviewee in this session",
        )
    _stash_session_timezone(request, review_session)
    return matched, review_session


def require_observer_in_session(
    session_id: int,
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> tuple[Observer, ReviewSession]:
    """403 unless the authenticated user has an active Observer row
    in the session.

    Identity match is case-insensitive email equality. Observer rows
    whose ``status`` is anything other than ``active`` do not grant
    access. Unlike reviewees, observers always carry an email
    (``observers.email`` is NOT NULL) so no parse check is needed.

    Phase 1 stub — defined but not referenced by any route yet. The
    observer collation surface (Phase 3 W17) wires this in.
    """
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    user_email = (user.email or "").casefold()
    candidates = db.execute(
        select(Observer).where(
            Observer.session_id == session_id,
            Observer.status == "active",
        )
    ).scalars()
    matched: Observer | None = None
    for o in candidates:
        if o.email.casefold() == user_email:
            matched = o
            break
    if matched is None:
        log.warning(
            "permission denied",
            extra={
                "gate": "require_observer_in_session",
                "user_id": user.id,
                "session_id": session_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active observer in this session",
        )
    _stash_session_timezone(request, review_session)
    return matched, review_session


def request_correlation_id() -> str:
    return uuid.uuid4().hex
