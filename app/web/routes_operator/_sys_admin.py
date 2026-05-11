"""Sys Admin chrome — Segment 16A PR 2.

Empty-shell route for the per-session Sys Admin landing. The body
is intentionally bare; PRs 3-6 fill it in:

- PR 3 — Outbox card lifts the existing
  ``GET /operator/sessions/{id}/outbox`` content under this chrome.
- PR 4 — Audit log download tile wires the existing
  ``GET /operator/sessions/{id}/export/audit_log.csv`` route.
- PR 5 — Pure-removal PR (manual-assignment path retires); no
  surface change here.
- PR 6 — Sibling workspace-scoped Sys Admin URL plus the user-
  list / Admit / Revoke / Promote / Demote toggles.

The route gates on ``require_sys_admin`` (full 403 on miss) and
``require_session_operator`` (so the per-session membership check
continues to compose). The outer ``require_operator`` on the
parent operator ``APIRouter`` (PR 1b) is redundant for sys-admins
but harmless — sys-admin implies operator at the predicate level
(F4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.web import breadcrumbs, views
from app.web.deps import require_session_operator, require_sys_admin
from app.web.routes_operator._shared import _templates


router = APIRouter()


@router.get(
    "/sessions/{session_id}/sys-admin",
    response_class=HTMLResponse,
)
def session_sys_admin(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    return _templates.TemplateResponse(
        request,
        "operator/session_sys_admin.html",
        {
            "session": review_session,
            "user": user,
            "current_page": "Sys Admin",
            "status_pills": views.session_status_pills(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Sys Admin"
            ),
        },
    )
