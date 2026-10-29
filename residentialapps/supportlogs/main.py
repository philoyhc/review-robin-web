"""The Support Logs factory, `residentialapps.supportlogs.main:create_app`, named by
Cordware's registry entry `supportlogs`."""

from __future__ import annotations

from fastapi import FastAPI

from residentialapps.supportlogs.routes_frontline import router as frontline_router
from residentialapps.supportlogs.routes_health import router as health_router
from residentialapps.supportlogs.routes_home import router as home_router
from residentialapps.supportlogs.routes_pages import router as pages_router


def create_app() -> FastAPI:
    # No schema pages: neither application is an API, and they would list
    # its routes to anyone signed out.
    app = FastAPI(title="Support Logs", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health_router)
    app.include_router(home_router)
    app.include_router(frontline_router)
    app.include_router(pages_router)
    return app
