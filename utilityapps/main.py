"""The Utilities factory, `utilityapps.main:create_app`, named by Cordware's
registry entry `utilities` (segment U1, rung 1)."""

from __future__ import annotations

from fastapi import FastAPI

from utilityapps.email_check.routes import router as email_check_router
from utilityapps.routes_health import router as health_router
from utilityapps.routes_home import router as home_router


def create_app() -> FastAPI:
    # No schema pages, as Residential's: not an API, and they would list
    # its routes to anyone signed out.
    app = FastAPI(title="Cordware Utilities", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health_router)
    app.include_router(home_router)
    app.include_router(email_check_router)
    return app
