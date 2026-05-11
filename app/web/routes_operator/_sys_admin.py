"""Sys Admin chrome — Segment 16A.

Workspace-level Admin surfaces.

**PR 2 / 2b (#841 / #842).** Landed the empty-shell route at
``GET /operator/sys-admin`` reached via the top-bar "Admin"
link. Body was an empty shell.

**PR 3 + PR 4.** The shell becomes a 303 redirect to the
default tab. First tab — Sessions Diagnostics — lives at
``GET /operator/sys-admin/sessions`` and renders the workspace
sessions table with per-row Outbox + Audit log actions.

**This slice (Outbox inline reshape).** Clicking the per-row
Outbox link no longer navigates to a separate per-session
page; the click sets ``?outbox_session_id=N`` on the Admin URL
and the outbox content renders below the table on the same
page (`#outbox` anchor for scroll). The per-session
``/operator/sessions/{id}/outbox`` route is retired.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import invitations, sessions
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
    outbox_session_id: int | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    target = resolve_return_to(return_to, db)

    outbox_session: ReviewSession | None = None
    outbox_rows: list[object] = []
    if outbox_session_id is not None:
        outbox_session = db.execute(
            select(ReviewSession).where(ReviewSession.id == outbox_session_id)
        ).scalar_one_or_none()
        if outbox_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        outbox_rows = invitations.list_outbox_for_session(
            db, outbox_session.id
        )

    return _templates.TemplateResponse(
        request,
        "operator/sys_admin_sessions.html",
        {
            "user": user,
            "sessions": sessions.list_all(db),
            "return_to_raw": return_to,
            "return_to_url": target.url,
            "return_to_label": target.label,
            "outbox_session": outbox_session,
            "outbox_rows": outbox_rows,
        },
    )
