"""The ApplyDesk factory, `applydesk.main:create_app`, named by Cordware's
registry entry `applydesk` (segment AD1)."""

from __future__ import annotations

from fastapi import FastAPI

from applydesk.routes_health import router as health_router
from applydesk.routes_home import router as home_router
from applydesk.routes_me import router as me_router
from applydesk.routes_operator import router as operator_router


def create_app() -> FastAPI:
    # No schema pages, as Residential's and Utilities': not an API, and they
    # would list its routes to anyone signed out.
    app = FastAPI(title="ApplyDesk", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health_router)
    app.include_router(home_router)
    app.include_router(operator_router)
    app.include_router(me_router)
    return app
