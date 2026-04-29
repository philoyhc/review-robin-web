from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


@router.get("/about", response_class=HTMLResponse)
def about(request: Request) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "about.html",
        {"user": None, "breadcrumbs": []},
    )
