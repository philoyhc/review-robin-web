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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from cordware.identity import is_local

from app.web import urls
from app.auth.roles import super_admin_configured
from app.db.models import User
from app.db.session import get_db
from app.services import (
    account_listing,
    audit,
    directory_accounts,
    invitations,
    operator_settings,
    permissions,
    session_owners,
    sessions,
    users as users_service,
)
from app.web import views
from app.web.deps import request_correlation_id, require_sys_admin
from app.web.return_to import ReturnTarget, resolve_return_to
from app.web.routes_operator._shared import _templates, directory_or_none


router = APIRouter()


# Where the Admin pages' back link returns to (author, 2026-10-14): the
# page the chrome's Admin link was followed from, remembered for the
# visit so both tabs, and every action's redirect, keep it. Validated on
# the way in and again on the way out (``resolve_return_to``).
_ADMIN_RETURN_COOKIE = "rrw-admin-return-to"
_ADMIN_PATH = "/operator/sys-admin"


def _admin_return_target(
    request: Request, return_to: str | None, db: Session, user: User
) -> ReturnTarget:
    return resolve_return_to(
        return_to or request.cookies.get(_ADMIN_RETURN_COOKIE),
        db,
        viewer=user,
        routes=request.app.routes,
    )


def _remember_return_to(request: Request, response: Response, target: ReturnTarget) -> None:
    response.set_cookie(
        _ADMIN_RETURN_COOKIE,
        target.url,
        path=urls.cookie_path(request, _ADMIN_PATH),
        httponly=True,
        samesite="lax",
    )


@router.get("/sys-admin")
def sys_admin_root(
    request: Request,
    return_to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect to the default Admin tab (Sessions Diagnostics),
    remembering ``?return_to=`` for both tabs' back link."""
    target = f"{_ADMIN_PATH}/sessions"
    if return_to:
        target = f"{target}?return_to={quote(return_to, safe='/')}"
    response = urls.redirect(request, url=target, status_code=status.HTTP_303_SEE_OTHER)
    if return_to:
        _remember_return_to(request, response, _admin_return_target(request, return_to, db, user))
    return response


_DIAGNOSTICS_SORT_COOKIE = "rrw-sort-sys-admin-sessions"


@router.get("/sys-admin/sessions", response_class=HTMLResponse)
def sys_admin_sessions(
    request: Request,
    return_to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    target = _admin_return_target(request, return_to, db, user)
    # The lobby's columns and sort (author, 2026-10-14): a cookie-backed
    # personal sort, seeded here so the first render is already sorted.
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=_DIAGNOSTICS_SORT_COOKIE,
        valid_keys=views.DIAGNOSTICS_SORT_KEYS,
    )
    rows = views.apply_cookie_sort(
        sessions.list_all(db), sort_spec, value_resolver=views.session_sort_value
    )
    owners = session_owners.owners_by_session(db, [s.id for s in rows])
    response = _templates.TemplateResponse(
        request,
        "operator/sys_admin_sessions.html",
        {
            "user": user,
            "sessions": rows,
            "session_counts": views.session_status_counts(rows),
            "sort_cookie": _DIAGNOSTICS_SORT_COOKIE,
            # The filter matches name, code and owner; the text it
            # matches rides each row.
            "filter_text_by_session": {
                s.id: views.diagnostics_filter_text(s, owners.get(s.id, []))
                for s in rows
            },
            "filter_options": views.diagnostics_filter_options(rows, owners),
            "owned_session_ids": views.owned_session_ids(owners, user),
            "return_to_raw": return_to,
            "return_to_url": target.url,
            "return_to_label": target.label,
        },
    )
    if return_to:
        _remember_return_to(request, response, target)
    return response


@router.get(
    "/sys-admin/sessions/{session_id}/outbox",
    response_class=HTMLResponse,
)
def sys_admin_session_outbox(
    request: Request,
    session_id: str,
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Child page under Sessions Diagnostics. The back-link points
    at /operator/sys-admin/sessions; the Admin chrome's
    Sessions Diagnostics tab stays highlighted."""
    review_session = sessions.get_by_public_id(db, session_id)
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
    session_id: str,
    cursor: int | None = Query(default=None, ge=1),
    event_type: list[str] | None = Query(default=None),
    severity: list[str] | None = Query(default=None),
    actor: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    tz: str | None = Query(default=None),
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

    ``?tz=utc`` reads the page in UTC; without it, in the viewer's
    Settings timezone (``views.resolve_audit_log_zone``).
    """
    review_session = sessions.get_by_public_id(db, session_id)
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    zone = views.resolve_audit_log_zone(
        tz, operator_settings.get_display_timezone(user)
    )
    try:
        filters = views.parse_audit_log_filters(
            event_types=event_type,
            severities=severity,
            actor=actor,
            from_=from_,
            to=to,
            date_zone=zone.tz_name,
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
        f"/operator/sys-admin/sessions/{review_session.public_id}/audit-log"
    )
    csv_base_url = (
        f"/operator/sessions/{review_session.public_id}/export/audit_log.csv"
    )
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_session_audit_log.html",
        {
            "user": user,
            "audit_session": review_session,
            "audit_log": views.build_audit_log_rows(
                rows, limit=_AUDIT_LOG_PAGE_SIZE, tz_name=zone.tz_name
            ),
            "filter_form": views.build_audit_log_filter_form(
                filters,
                distinct_actor_emails=audit.list_distinct_actor_emails(
                    db, review_session
                ),
                base_url=base_url,
                csv_base_url=csv_base_url,
                zone=zone,
            ),
            "filters_querystring": views.filters_querystring(filters, zone),
            "viewer_base_url": base_url,
        },
    )


# ---- Accounts Management (PR 6) ------------------------------------------


_ACCOUNTS_URL = "/operator/sys-admin/users"
_ONE_YEAR = 365 * 24 * 60 * 60


@router.get("/sys-admin/users", response_class=HTMLResponse)
def sys_admin_users(
    request: Request,
    invite_error: str | None = Query(default=None),
    invite_unchecked: str | None = Query(default=None),
    toggle_error: str | None = Query(default=None),
    refused: int | None = Query(default=None),
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
    # ``?selected=`` row an action just changed turns its chip on, as if
    # clicked, and lands on its page, so the operator sees what they did.
    # No ``show`` in the URL (the tab strip, the chrome, a bare link)
    # takes the chips last asked for (author, 2026-10-14); an explicit
    # one, even every chip off, is remembered for next time.
    chips = show if show is not None else views.remembered_account_chips(
        request.cookies.get(views.ACCOUNT_CHIPS_COOKIE)
    )
    view = views.parse_account_view(show=chips, role=role, search=q, offset=offset)
    if selected is not None:
        selected_category = account_listing.category_of(db, selected)
        if selected_category is not None:
            view = view.with_category(selected_category)
    # After ``selected``: a chip it turned on is remembered, as a click is.
    remembered = views.account_chips_cookie(view)
    page = account_listing.list_accounts_page(
        db,
        categories=view.show,
        role=None if view.role == "any" else view.role,
        search=view.search,
        offset=view.offset,
        page_size=views.PAGE_SIZE,
        selected_user_id=selected,
    )
    view = dataclasses.replace(view, offset=page.offset)
    pager = views.build_pager(total=page.total, offset=page.offset)
    refused_user = db.get(User, refused) if refused is not None else None
    back = _admin_return_target(request, None, db, user)
    response = _templates.TemplateResponse(
        request,
        "operator/sys_admin_users.html",
        {
            "user": user,
            # The back link returns where the Admin visit began, as on
            # Sessions Diagnostics (author, 2026-10-14).
            "return_to_url": back.url,
            "return_to_label": back.label,
            "rows": page.rows,
            "account_view": view,
            # The whole workspace, for the empty-state wording: no
            # accounts at all reads differently from none matching.
            "account_total": sum(page.counts.values()),
            "account_chips": views.build_account_chips(page.counts, view),
            # admin_pages_refine Item 3 — the Overview card: the chips'
            # own counts on one line, and the super-admins.
            "account_overview_pills": views.build_account_overview_pills(
                page.counts, super_admins=account_listing.count_super_admins(db)
            ),
            "account_role_options": views.ACCOUNT_ROLE_OPTIONS,
            # The typeahead's first list, for what the box already holds;
            # the page's script asks ``search-options`` again as it changes.
            "account_search_options": account_listing.search_options(
                db, categories=view.show, search=view.search
            ),
            # The query the action forms post back, so their redirect
            # keeps the chips, role, search and page.
            "account_view_query": views.account_view_query(view),
            # Clear drops the role and the search; the chips stay.
            "account_view_query_chips": views.account_view_query(
                dataclasses.replace(view, role="any", search="", offset=0)
            ),
            "accounts_base_url": _ACCOUNTS_URL,
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
                f"{_ACCOUNTS_URL}?"
                + views.account_view_query(view, offset=False)
                + "&"
            ),
            "pager_anchor": "accounts-table-card",
            "actor_is_super_admin": user.is_super_admin,
            # Segment 18S Item 2 — the Promote/Demote controls follow the
            # same rule as the service actor guard: a super-admin actor,
            # OR (no super tier configured) any admin, so the UI never
            # hides a control the server would actually accept.
            "can_manage_admins": (
                user.is_super_admin or not super_admin_configured()
            ),
            "invite_error": invite_error,
            "invite_unchecked": bool(invite_unchecked),
            # A refused batch names its row: the email is looked up, the
            # reason comes from the view's own table, never from the URL.
            "toggle_message": views.account_refusal_message(
                toggle_error, refused_user.email if refused_user else None
            )
            if toggle_error
            else None,
            "selected_user_id": selected,
        },
    )
    response.set_cookie(
        views.ACCOUNT_CHIPS_COOKIE,
        remembered,
        max_age=_ONE_YEAR,
        path=urls.cookie_path(request, _ACCOUNTS_URL),
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/sys-admin/users/search-options")
def sys_admin_users_search_options(
    show: list[str] | None = Query(default=None),
    q: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> JSONResponse:
    # admin_pages_refine Item 1 — the search box's typeahead, asked again
    # as the operator types: up to 200 matches under the chips, so
    # any account can be suggested, however late in the alphabet.
    view = views.parse_account_view(show=show, role=None, search=q, offset=0)
    return JSONResponse(
        account_listing.search_options(
            db, categories=view.show, search=view.search
        )
    )


@router.post("/sys-admin/sessions/{session_id}/adopt")
def sys_admin_adopt_session(
    request: Request, session_id: str,
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
    review_session = sessions.get_by_public_id(db, session_id)
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not permissions.user_can_view_session(db, actor, review_session.id):
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
    return urls.redirect(request,
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
    request: Request, error_code: str | None = None,
    selected_user_id: int | None = None,
    view: str = "",
    refused_user_id: int | None = None,
    invite_unchecked: bool = False,
) -> RedirectResponse:
    """Back to Accounts. ``view`` is the query the action form posted
    (admin_pages_refine Item 1): parsed and re-encoded rather than
    echoed, so the redirect keeps the chips, role, search and page and
    nothing else."""
    url = _ACCOUNTS_URL
    params: list[str] = []
    if view:
        params.append(
            views.account_view_query(views.account_view_from_query(view))
        )
    if error_code:
        params.append(f"toggle_error={quote(error_code, safe='')}")
    if refused_user_id is not None:
        params.append(f"refused={refused_user_id}")
    if selected_user_id is not None:
        params.append(f"selected={selected_user_id}")
    if invite_unchecked:
        params.append("invite_unchecked=1")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return urls.redirect(request, url=url, status_code=status.HTTP_303_SEE_OTHER)


def _handle_toggle(
    request: Request,
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
    return _users_redirect(request, selected_user_id=selected_user_id, view=view)


@router.post("/sys-admin/users/{user_id}/admit")
def admit_user(
    request: Request, user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(request,
        users_service.admit,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/revoke")
def revoke_user(
    request: Request, user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(request,
        users_service.revoke,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/promote")
def promote_user(
    request: Request, user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(request,
        users_service.promote,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/demote")
def demote_user(
    request: Request, user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(request,
        users_service.demote,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/remove-from-all-sessions")
def remove_from_all_sessions(
    request: Request, user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return _handle_toggle(request,
        users_service.remove_from_all_sessions,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        selected_user_id=user_id,
        view=view,
    )


@router.post("/sys-admin/users/{user_id}/delete")
def remove_user(
    request: Request, user_id: int,
    view: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # ``remove_user`` deletes the row outright, so there's no row
    # to re-select on the redirect target.
    return _handle_toggle(request,
        users_service.remove_user,
        db=db,
        actor=actor,
        target=_load_target(db, user_id),
        view=view,
    )


#: The row expander's routes (admin_pages_refine Item 2): the path
#: segment after ``bulk-``, mapped to ``users.apply_batch``'s action.
_BULK_ACTIONS: dict[str, str] = {
    "admit": "admit",
    "revoke": "revoke",
    "remove-from-all-sessions": "remove_from_all_sessions",
    "promote": "promote",
    "demote": "demote",
    "delete": "delete",
}


@router.post("/sys-admin/users/bulk-{action}")
def bulk_account_action(
    request: Request, action: str,
    user_ids: list[int] = Form(default_factory=list),
    view: str = Form(default=""),
    confirm: str = Form(default=""),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """One action on the selected rows, all or nothing
    (``users.apply_batch``). A refusal changes nothing and comes back to
    the page naming the row and the reason; Delete also needs the
    expander's confirm, like the roster pages' ``bulk-delete``."""
    batch_action = _BULK_ACTIONS.get(action)
    if batch_action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if batch_action == "delete" and confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tick the confirmation to delete the selected accounts.",
        )
    try:
        users_service.apply_batch(
            db,
            actor=actor,
            action=batch_action,
            user_ids=user_ids,
            correlation_id=request_correlation_id(),
        )
    except users_service.UserOperationError as exc:
        db.rollback()
        if exc.code in {"self_action", "empty_selection"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
            ) from exc
        if exc.code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
            ) from exc
        if exc.code == "requires_super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=exc.message
            ) from exc
        return _users_redirect(request,
            error_code=exc.code, refused_user_id=exc.user_id, view=view
        )
    # One row keeps the single-row actions' landing: its chip on, its
    # page open. Several have no one row to land on; a delete, none left.
    single = len(set(user_ids)) == 1 and batch_action != "delete"
    return _users_redirect(request,
        selected_user_id=user_ids[0] if single else None, view=view
    )


@router.get("/sys-admin/users/directory-search")
def invite_directory_search(
    request: Request,
    q: str = "",
    actor: User = Depends(require_sys_admin),
) -> JSONResponse:
    """The invite box's picker (19Z, invite from the directory): up to ten
    people whose name, surname, mail or sign-in name starts with ``q``,
    asked on the admin's own token. ``available`` is false when the
    directory cannot be asked, so the box says so rather than "no
    match", and ``reason`` says why (the failure's kind, status and
    Graph's error code), for the admin to read. Not audited (author,
    2026-11-01)."""
    found = directory_accounts.search(directory_or_none(request), q)
    answer: dict[str, object] = {
        "available": found.people is not None,
        "people": [
            {"name": p.name, "mail": p.mail, "upn": p.upn, "address": p.address}
            for p in (found.people or [])
        ],
    }
    if found.reason:
        answer["reason"] = found.reason
    return JSONResponse(
        answer,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/sys-admin/users/invite")
def invite_user(
    request: Request, email: str = Form(...),
    invite_as_sys_admin: str | None = Form(default=None),
    actor: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # Checked against the directory on the inviting admin's own token
    # (segment 19Z, accounts item); no token or a failed lookup checks
    # nothing, and the row is created unbound, as before. A local run's
    # directory is the five fake people, and the accounts invited there
    # are made up, so it checks nothing either. The picker fills
    # "Name <address>"; the address in the brackets is the one invited.
    name, address = users_service.split_named_address(email)

    def look_up():
        directory = None if is_local() else directory_or_none(request)
        return directory_accounts.look_up_one(directory, address)

    try:
        invited = users_service.invite(
            db,
            actor=actor,
            email=address,
            is_operator=True,
            is_sys_admin=invite_as_sys_admin == "true",
            directory=look_up,
            display_name=name,
        )
    except users_service.UserOperationError as exc:
        url = f"{_ACCOUNTS_URL}?invite_error={quote(exc.code, safe='')}"
        return urls.redirect(request, url=url, status_code=status.HTTP_303_SEE_OTHER)
    # Selected, so its chip turns on whatever chips are remembered.
    return _users_redirect(
        request, selected_user_id=invited.id,
        invite_unchecked=invited.external_principal_id is None,
    )
