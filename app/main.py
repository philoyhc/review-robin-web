from fastapi import FastAPI

from app.config import settings
from app.web.routes_health import router as health_router


app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.include_router(health_router)
