"""Sys Admin chrome — Segment 16A PR 2 (workspace-level reshape).

Empty-shell workspace-level landing at ``GET /operator/sys-admin``.
The body is intentionally bare; PRs 3-6 fill it:

- PR 3 — Outbox tile (per-session content surfaced via a
  session picker on this page).
- PR 4 — Audit log CSV download (per-session via the same
  picker, wired to the existing
  ``GET /operator/sessions/{id}/export/audit_log.csv`` route).
- PR 5 — Pure-removal PR (manual-assignment path retires); no
  new surface here.
- PR 6 — Workspace user list (Admit / Revoke / Promote /
  Demote) as a sibling section on this same page or a
  ``/operator/sys-admin/users`` child — decided at PR 6 time.

The route gates on ``require_sys_admin`` (full 403 on miss).
The outer ``require_operator`` on the parent operator
``APIRouter`` (PR 1b) is redundant for sys-admins but harmless
— sys-admin implies operator at the predicate level (F4).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.web.deps import require_sys_admin
from app.web.return_to import resolve_return_to
from app.web.routes_operator._shared import _templates


router = APIRouter()


@router.get("/sys-admin", response_class=HTMLResponse)
def sys_admin_landing(
    request: Request,
    return_to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> Response:
    target = resolve_return_to(return_to, db)
    return _templates.TemplateResponse(
        request,
        "operator/sys_admin.html",
        {
            "user": user,
            "return_to_raw": return_to,
            "return_to_url": target.url,
            "return_to_label": target.label,
        },
    )
