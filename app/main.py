from fastapi import FastAPI

from app.web.routes_auth import router as auth_router
from app.web.routes_health import router as health_router
from app.web.routes_operator import router as operator_router
from app.web.routes_reviewer import router as reviewer_router


def create_app() -> FastAPI:
    app = FastAPI(title="Review Robin Web")
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(operator_router)
    app.include_router(reviewer_router)

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "Review Robin Web",
            "status": "ok",
            "health": "/health",
            "docs": "/docs",
        }

    return app


app = create_app()
