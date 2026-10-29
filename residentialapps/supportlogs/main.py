"""The Support Logs factory, `residentialapps.supportlogs.main:create_app`, named by
Cordware's registry entry `supportlogs`."""

from __future__ import annotations

from fastapi import FastAPI

from residentialapps.supportlogs.routes_consultation import router as consultation_router
from residentialapps.supportlogs.routes_frontline import router as frontline_router
from residentialapps.supportlogs.routes_health import router as health_router
from residentialapps.supportlogs.routes_home import router as home_router
from residentialapps.supportlogs.routes_overview import router as overview_router
from residentialapps.supportlogs.routes_plans import router as plans_router
from residentialapps.supportlogs.routes_safety import router as safety_router
from residentialapps.supportlogs.routes_sys_admin import router as sys_admin_router


def create_app() -> FastAPI:
    # No schema pages: neither application is an API, and they would list
    # its routes to anyone signed out.
    app = FastAPI(title="Support Logs", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health_router)
    app.include_router(home_router)
    app.include_router(frontline_router)
    app.include_router(safety_router)
    app.include_router(plans_router)
    app.include_router(overview_router)
    app.include_router(consultation_router)
    app.include_router(sys_admin_router)
    return app
