from fastapi import FastAPI

from app.web.routes_health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Review Robin Web")
    app.include_router(health_router)

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
