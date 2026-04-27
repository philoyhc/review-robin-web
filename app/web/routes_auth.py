from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth.identity import (
    AuthenticatedUser,
    extract_claims,
    get_current_user,
)

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/me")
def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, object]:
    return {
        "principal_id": user.principal_id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "is_fake": user.is_fake,
    }


@router.get("/me/debug", response_class=HTMLResponse)
def me_debug(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "me_debug.html",
        {"user": user, "claims": extract_claims(request)},
    )
