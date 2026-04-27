from fastapi import FastAPI

from app.web.routes_health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Review Robin Web")
    app.include_router(health_router)
    return app


app = create_app()
