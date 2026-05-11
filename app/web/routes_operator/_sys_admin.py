"""Sys Admin chrome — Segment 16A.

Workspace-level Admin surfaces.

**PR 2 / 2b (#841 / #842).** Landed the empty-shell route at
``GET /operator/sys-admin`` reached via the top-bar "Admin"
link.

**PR 3 + PR 4.** Filled in the first tab — Sessions Diagnostics
— at ``GET /operator/sys-admin/sessions`` rendering the
workspace sessions table.

**Outbox reshape.** Per-session Outbox lives on a child page at
``GET /operator/sys-admin/sessions/{session_id}/outbox``.

**PR 6 (this slice).** Lights up the second tab — Accounts
Management — at ``GET /operator/sys-admin/users`` with per-row
Admit / Revoke / Promote / Demote toggles and a sibling "Invite
by email" form. Backed by ``app.services.users``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import audit, invitations, sessions, users as users_service
from app.web import views
from app.web.deps import require_sys_admin
from app.web.return_to import resolve_return_to
from app.web.routes_operator._shared import _templates


router = APIRouter()


@router.get("/sys-admin")
def sys_admin_root(
    return_to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
) -> RedirectResponse:
    """Redirect to the default Admin tab (Sessions Diagnostics).
    Preserves ``?return_to=`` so the eventual landing page's back
    link still resolves to the originating page."""
    target = "/operator/sys-admin/sessions"
    if return_to:
        target = f"{target}?return_to={quote(return_to, safe='/')}"
    return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/sys-admin/sessions", response_class=HTMLResponse)
def sys_admin_sessions(
    request: Request,
    return_to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    target = resolve_return_to(return_to, db)
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_sessions.html",
        {
            "user": user,
            "sessions": sessions.list_all(db),
            "return_to_raw": return_to,
            "return_to_url": target.url,
            "return_to_label": target.label,
        },
    )


@router.get(
    "/sys-admin/sessions/{session_id}/outbox",
    response_class=HTMLResponse,
)
def sys_admin_session_outbox(
    request: Request,
    session_id: int,
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Child page under Sessions Diagnostics. The back-link points
    at /operator/sys-admin/sessions; the Admin chrome's
    Sessions Diagnostics tab stays highlighted."""
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_session_outbox.html",
        {
            "user": user,
            "outbox_session": review_session,
            "outbox_rows": invitations.list_outbox_for_session(
                db, review_session.id
            ),
        },
    )


_AUDIT_LOG_PAGE_SIZE = 50


@router.get(
    "/sys-admin/sessions/{session_id}/audit-log",
    response_class=HTMLResponse,
)
def sys_admin_session_audit_log(
    request: Request,
    session_id: int,
    cursor: int | None = Query(default=None, ge=1),
    event_type: list[str] | None = Query(default=None),
    severity: list[str] | None = Query(default=None),
    actor: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Per-session audit log child page (Segment 16C PR 1 + PR 2).

    Sibling of the Outbox child page — same chrome, same back-link
    convention. Newer-first table with keyset pagination on
    ``id DESC``; the previous page's last ``id`` arrives as
    ``?cursor=<id>`` and the next page asks for ``id < cursor``.

    PR 2 adds a filter strip: ``?event_type=`` (multi),
    ``?severity=`` (multi), ``?actor=`` (single), ``?from=`` /
    ``?to=`` (ISO date). Filter state composes with the cursor;
    the Download CSV button carries the same query string so the
    spreadsheet honours the filter set.
    """
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        filters = views.parse_audit_log_filters(
            event_types=event_type,
            severities=severity,
            actor=actor,
            from_=from_,
            to=to,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"audit log filter parsing failed: {exc}",
        ) from exc
    rows = audit.list_events_for_session(
        db,
        review_session,
        cursor=cursor,
        limit=_AUDIT_LOG_PAGE_SIZE,
        filters=filters,
    )
    base_url = (
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    csv_base_url = (
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
    )
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_session_audit_log.html",
        {
            "user": user,
            "audit_session": review_session,
            "audit_log": views.build_audit_log_rows(
                rows, limit=_AUDIT_LOG_PAGE_SIZE
            ),
            "filter_form": views.build_audit_log_filter_form(
                filters,
                distinct_actor_emails=audit.list_distinct_actor_emails(
                    db, review_session
                ),
                base_url=base_url,
                csv_base_url=csv_base_url,
            ),
            "filters_querystring": views.filters_querystring(filters),
            "viewer_base_url": base_url,
        },
    )


# ---- Accounts Management (PR 6) ------------------------------------------


@router.get("/sys-admin/users", response_class=HTMLResponse)
def sys_admin_users(
    request: Request,
    invite_error: str | None = Query(default=None),
    toggle_error: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_users.html",
        {
            "user": user,
            "rows": users_service.list_workspace_users(db),
            "invite_error": invite_error,
            "toggle_error": toggle_error,
        },
    )


def _load_target(db: Session, user_id: int) -> User:
    target = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return target


def _users_redirect(error_code: str | None = None) -> RedirectResponse:
    url = "/operator/sys-admin/users"
    if error_code:
        url = f"{url}?toggle_error={quote(error_code, safe='')}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _handle_toggle(
    action: Callable[..., Any], /, **kwargs: Any
) -> RedirectResponse:
    try:
        action(**kwargs)
    except users_service.UserOperationError as exc:
        if exc.code == "self_action":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
            ) from exc
        if exc.code == "last_admin":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=exc.message
            ) from exc
        raise
    return _users_redirect()


@router.post("/sys-admin/users/{user_id}/admit")
def admit_user(
    user_id: int,
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.admit, db=db, actor=actor, target=_load_target(db, user_id)
    )


@router.post("/sys-admin/users/{user_id}/revoke")
def revoke_user(
    user_id: int,
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.revoke, db=db, actor=actor, target=_load_target(db, user_id)
    )


def _require_confirm(confirm: str | None) -> None:
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required for high-risk role changes",
        )


@router.post("/sys-admin/users/{user_id}/promote")
def promote_user(
    user_id: int,
    confirm: str | None = Form(default=None),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_confirm(confirm)
    return _handle_toggle(
        users_service.promote, db=db, actor=actor, target=_load_target(db, user_id)
    )


@router.post("/sys-admin/users/{user_id}/demote")
def demote_user(
    user_id: int,
    confirm: str | None = Form(default=None),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_confirm(confirm)
    return _handle_toggle(
        users_service.demote, db=db, actor=actor, target=_load_target(db, user_id)
    )


@router.post("/sys-admin/users/invite")
def invite_user(
    email: str = Form(...),
    invite_as_sys_admin: str | None = Form(default=None),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        users_service.invite(
            db,
            actor=actor,
            email=email,
            is_operator=True,
            is_sys_admin=invite_as_sys_admin == "true",
        )
    except users_service.UserOperationError as exc:
        url = f"/operator/sys-admin/users?invite_error={quote(exc.code, safe='')}"
        return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)
    return _users_redirect()
