from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.web.deps import get_or_create_user
from app.web.return_to import resolve_return_to

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


@router.get("/about", response_class=HTMLResponse)
def about(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # /about doubles as the "signed in but no access" landing since 18R
    # Item 6 retired /request-access: it carries the app description plus a
    # "getting access" note (identity + operator contact). Passing the real
    # user renders the chrome's identity + Sign out for a stranger who'd
    # otherwise be stuck without a way to see who they are or sign out.
    #
    # Depends on the **persisted** ``User`` row, not the header-derived
    # ``AuthenticatedUser`` (19F PR 3). Two reasons, both found by
    # rendering the page rather than reading it:
    #
    # 1. The chrome's "Signed in as …" reads ``user.display_label``,
    #    which only the row has — so this page had been rendering that
    #    line with an **empty name**. Exactly the defect 19E rung 7
    #    found and fixed on ``/guide``; the sibling route was never
    #    re-checked.
    # 2. ``get_or_create_user`` stamps the flag that hides the chrome's
    #    Guide link for a viewer with no Guide audiences. Without it,
    #    a stranger bounced here *from* ``/guide`` is offered a link
    #    straight back to the page that bounced them.
    return_to = resolve_return_to(request.query_params.get("return_to"), db)
    return _templates.TemplateResponse(
        request,
        "about.html",
        {
            "user": user,
            "breadcrumbs": [],
            "return_to_url": return_to.url,
            "return_to_label": return_to.label,
            "contact_email": settings.operator_contact_email,
        },
    )
