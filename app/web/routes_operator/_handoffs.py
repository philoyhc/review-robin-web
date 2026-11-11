"""Handoffs from another Cordware application (segment 23A).

The proof of concept's RRW side: a holding page that another
application opens in a new tab during its operator's click, while it
posts the setup that creates the session, then moves the tab to that
session's Session Home (`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
§7.1). The create route itself is in ``_quick_setup.py``, whose
pipeline it runs (slices do not import one another).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.db.models import User
from app.web import breadcrumbs
from app.web.deps import get_or_create_user
from app.web.routes_operator._shared import _templates

router = APIRouter()

#: Never cached: the page stands in while a session is created.
_NO_STORE = {"Cache-Control": "no-store"}


@router.get("/handoffs/new", response_class=HTMLResponse)
def handoff_holding(request: Request, user: User = Depends(get_or_create_user)) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/handoff_new.html",
        {"user": user, "breadcrumbs": breadcrumbs.operator_sessions_child("New session")},
        headers=_NO_STORE,
    )
