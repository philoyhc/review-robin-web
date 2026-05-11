"""Sys Admin chrome — Segment 16A.

Workspace-level Admin surfaces.

**PR 2 / 2b (#841 / #842).** Landed the empty-shell route at
``GET /operator/sys-admin`` reached via the top-bar "Admin"
link. Body was an empty shell.

**PR 3 (this slice).** The shell becomes a 303 redirect to the
default tab. First tab — Sessions Diagnostics — lives at
``GET /operator/sys-admin/sessions`` and renders the workspace
sessions table (one row per session in
``sessions.list_all(db)``) with a per-row "View outbox" link
pointing at the existing per-session
``/operator/sessions/{id}/outbox`` page. PR 4 adds an Audit log
column on the same table; PR 6 adds the Accounts Management
tab.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import sessions
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
