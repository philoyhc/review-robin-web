from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.config import settings
from app.db.session import get_db
from app.web.return_to import resolve_return_to

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


@router.get("/about", response_class=HTMLResponse)
def about(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # /about doubles as the "signed in but no access" landing since 18R
    # Item 6 retired /request-access: it carries the app description plus a
    # "getting access" note (identity + operator contact). Passing the real
    # user renders the chrome's identity + Sign out for a stranger who'd
    # otherwise be stuck without a way to see who they are or sign out.
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
