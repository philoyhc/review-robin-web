from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.identity import (
    AuthenticatedUser,
    extract_claims,
    get_current_user,
)
from app.config import settings
from app.db.session import get_db
from app.web.return_to import resolve_return_to

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


@router.get("/auth/me")
def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, object]:
    return {
        "principal_id": user.principal_id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "is_fake": user.is_fake,
    }


@router.get("/auth/me/debug", response_class=HTMLResponse)
def me_debug(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return_to = resolve_return_to(request.query_params.get("return_to"), db)
    return _templates.TemplateResponse(
        request,
        "me_debug.html",
        {
            "user": user,
            "claims": extract_claims(request),
            "return_to_url": return_to.url,
            "return_to_label": return_to.label,
        },
    )


@router.get("/request-access", response_class=HTMLResponse)
def request_access(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> HTMLResponse:
    """Landing page for an Easy Auth-admitted user who isn't on the
    operator allowlist (16A PR 1, F5). The ``require_operator``
    dependency redirects here via the ``OperatorAllowlistDenied``
    exception handler in ``app/main.py``.
    """
    return _templates.TemplateResponse(
        request,
        "request_access.html",
        {
            "user": user,
            "contact_email": settings.operator_contact_email,
        },
    )
