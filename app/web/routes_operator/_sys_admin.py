"""Sys Admin chrome — Segment 16A.

Workspace-level Admin surfaces.

**PR 2 / 2b (#841 / #842).** Landed the empty-shell route at
``GET /operator/sys-admin`` reached via the top-bar "Admin"
link.

**PR 3 + PR 4.** Filled in the first tab — Sessions Diagnostics
— at ``GET /operator/sys-admin/sessions`` rendering the
workspace sessions table.

**Outbox reshape (this slice).** Per-session Outbox lives on a
child page at
``GET /operator/sys-admin/sessions/{session_id}/outbox`` with a
"← Back to Sessions Diagnostics" affordance and the Admin
chrome's Sessions Diagnostics tab still highlighted. The
earlier inline ``?outbox_session_id=`` rendering on the
sessions page is gone — a child page sits cleaner than an
inline expanding region. The pre-16A per-session
``/operator/sessions/{id}/outbox`` route stays retired
(bookmarks 404 there).
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
