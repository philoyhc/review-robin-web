"""The RA Operations factory, `residentialapps.ops.main:create_app`, named by
Cordware's registry entry `residentialops`."""

from __future__ import annotations

from fastapi import FastAPI

from residentialapps.ops.routes_health import router as health_router


def create_app() -> FastAPI:
    # No schema pages: neither application is an API, and they would list
    # its routes to anyone signed out.
    app = FastAPI(title="RA Operations", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(health_router)
    return app
