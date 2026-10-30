"""The Utilities index at the bare mount: one card per tool
(`utilityapps/spec/utilities.md`). It names tools and holds nothing
about anyone, so it asks for no grant; each tool gates its own routes."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from utilityapps.web import templates

router = APIRouter()


@router.get("/", name="utilities_home")
def home(request: Request) -> Response:
    return templates.TemplateResponse(request, "utilities/index.html")
