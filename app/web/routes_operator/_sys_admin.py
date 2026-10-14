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

import dataclasses
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

from app.auth.roles import effective_super_admin_emails
from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import (
    account_listing,
    audit,
    invitations,
    permissions,
    session_owners,
    sessions,
    users as users_service,
)
from app.web import views
from app.web.deps import request_correlation_id, require_sys_admin
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
            # 19C Item 10 — the workspace-wide visibility-grid audit.
            # Read-only, and sys-admin-only by construction: it spans
            # every session, which no per-session operator may see.
            "visibility_audit_rows": views.build_visibility_audit_rows(db),
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
    selected: int | None = Query(default=None),
    show: list[str] | None = Query(default=None),
    role: str | None = Query(default=None),
    q: str | None = Query(default=None),
    offset: int = 0,
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    # admin_pages_refine Item 1 — the chips, the Session role, the search
    # and the page all filter in SQL (``account_listing``). A
    # ``?selected=`` row an action just changed turns its chip on for
    # this load and lands on its page, so the operator sees what they did.
    view = views.parse_account_view(show=show, role=role, search=q, offset=offset)
    if selected is not None:
        selected_category = account_listing.category_of(db, selected)
        if selected_category is not None:
            view = view.with_category(selected_category)
    page = account_listing.list_accounts_page(
        db,
        categories=view.show,
        role=None if view.role == "any" else view.role,
        search=view.search,
        offset=view.offset,
        selected_user_id=selected,
    )
    view = dataclasses.replace(view, offset=page.offset)
    pager = views.build_pager(total=page.total, offset=page.offset)
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_users.html",
        {
            "user": user,
            "rows": page.rows,
            "account_view": view,
            # The whole workspace, for the empty-state wording: no
            # accounts at all reads differently from none matching.
            "account_total": sum(page.counts.values()),
            "account_chips": views.build_account_chips(page.counts, view),
            "account_role_options": views.ACCOUNT_ROLE_OPTIONS,
            "account_search_options": account_listing.search_options(
                db, categories=view.show
            ),
            # The query the action forms post back, so their redirect
            # keeps the chips, role, search and page.
            "account_view_query": views.account_view_query(view),
            # Clear drops the role and the search; the chips stay.
            "account_view_query_chips": views.account_view_query(
                dataclasses.replace(view, role="any", search="", offset=0)
            ),
            "accounts_base_url": "/operator/sys-admin/users",
            "pager": pager,
            # Unlike the roster pages, the pager stays under a role or a
            # search: a role can match every account (Codex on #3025). So
            # the count line, which the roster pages show instead of a
            # pager, shows only when everything fits one page.
            "preview_count_line": None if pager else views.preview_count_line(
                shown=len(page.rows),
                pool=page.total,
                noun="accounts",
                is_filtered=view.is_filtered,
            ),
            "pager_url_base": (
                "/operator/sys-admin/users?"
                + views.account_view_query(view, offset=False)
                + "&"
            ),
            "pager_anchor": "accounts-table-card",
            # The Demote gate's ``last_admin`` count, workspace-wide.
            "sys_admin_count": users_service.sys_admin_count(db),
            "actor_is_super_admin": user.is_super_admin,
            # Segment 18S Item 2 — the Promote/Demote controls follow the
            # same rule as the service actor guard: a super-admin actor,
            # OR (no super tier configured) any admin, so the UI never
            # hides a control the server would actually accept.
            "can_manage_admins": (
                user.is_super_admin or not effective_super_admin_emails()
            ),
            "invite_error": invite_error,
            "toggle_error": toggle_error,
            "selected_user_id": selected,
        },
    )


@router.post("/sys-admin/sessions/{session_id}/adopt")
def sys_admin_adopt_session(
    session_id: int,
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Segment 18S Item 3 — the sys-admin cross-session elevation door.

    A sys-admin reaches a session they don't own from the Sessions
    Diagnostics list. Editing that session requires *ownership* (the
    per-session gate is no longer relaxed for sys-admins), so this
    action **self-adds the sys-admin as an owner** (audited
    ``session.owner_added``) and drops them on the session's Home,
    which they can now open through the normal operator path. Idempotent
    — a no-op when they already own it. This is the explicit, recorded
    elevation that replaces the old back-door edit access.
    """
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not permissions.user_can_view_session(db, actor, session_id):
        try:
            session_owners.add_owner(
                db,
                review_session=review_session,
                actor=actor,
                target=actor,
                correlation_id=request_correlation_id(),
            )
        except session_owners.OwnerOperationError:
            # already_owner race / not_in_workspace (a sys-admin is on the
            # allowlist, so the latter shouldn't fire) — fall through to the
            # redirect either way; the goal state is "actor owns it".
            pass
    return RedirectResponse(
        url=f"/operator/sessions/{session_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _load_target(db: Session, user_id: int) -> User:
    target = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return target


def _users_redirect(
    error_code: str | None = None,
    selected_user_id: int | None = None,
    view: str = "",
) -> RedirectResponse:
    """Back to Accounts. ``view`` is the query the action form posted
    (admin_pages_refine Item 1): parsed and re-encoded rather than
    echoed, so the redirect keeps the chips, role, search and page and
    nothing else."""
    url = "/operator/sys-admin/users"
    params: list[str] = []
    if view:
        params.append(
            views.account_view_query(views.account_view_from_query(view))
        )
    if error_code:
        params.append(f"toggle_error={quote(error_code, safe='')}")
    if selected_user_id is not None:
        params.append(f"selected={selected_user_id}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _handle_toggle(
    action: Callable[..., Any],
    /,
    *,
    selected_user_id: int | None = None,
    view: str = "",
    **kwargs: Any,
) -> RedirectResponse:
    try:
        action(**kwargs)
    except users_service.UserOperationError as exc:
        if exc.code == "self_action":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
            ) from exc
        if exc.code == "requires_super_admin":
            # Actor lacks super-admin — forbidden to manage admins
            # (Segment 18S Item 1).
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=exc.message
            ) from exc
        if exc.code in {
            "last_admin",
            "owns_sessions",
            "has_history",
            "still_owner",
            "sole_owner",
            "protected_super_admin",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=exc.message
            ) from exc
        raise
    return _users_redirect(selected_user_id=selected_user_id, view=view)


@router.post("/sys-admin/users/{user_id}/admit")
def admit_user(
    user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.admit,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/revoke")
def revoke_user(
    user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.revoke,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/promote")
def promote_user(
    user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.promote,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/demote")
def demote_user(
    user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.demote,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/remove-from-all-sessions")
def remove_from_all_sessions(
    user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(
        users_service.remove_from_all_sessions,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/delete")
def remove_user(
    user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # ``remove_user`` deletes the row outright, so there's no row
    # to re-select on the redirect target.
    return _handle_toggle(
        users_service.remove_user,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        view=view,
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
