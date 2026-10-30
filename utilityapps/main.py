"""The Utilities factory, `utilityapps.main:create_app`, named by Cordware's
registry entry `utilities` (segment U1, rung 1)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from utilityapps.email_check.routes import router as email_check_router
from utilityapps.routes_health import router as health_router
from utilityapps.routes_home import router as home_router
from utilityapps.web import templates


async def _http_error(request: Request, exc: HTTPException) -> Response:
    # A `403` is a page, not FastAPI's JSON (spec §3: a normal 403, not an
    # invitation to ask for access); anything else keeps the default.
    if exc.status_code == 403:
        return templates.TemplateResponse(request, "utilities/forbidden.html", status_code=403)
    return await http_exception_handler(request, exc)


def create_app() -> FastAPI:
    # No schema pages, as Residential's: not an API, and they would list
    # its routes to anyone signed out.
    app = FastAPI(title="Cordware Utilities", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_exception_handler(HTTPException, _http_error)
    app.include_router(health_router)
    app.include_router(home_router)
    app.include_router(email_check_router)
    return app
