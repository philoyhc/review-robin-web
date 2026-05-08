import re

from fastapi import FastAPI
from starlette.requests import Request

from app.web.routes_about import router as about_router
from app.web.routes_auth import router as auth_router
from app.web.routes_health import router as health_router
from app.web.routes_operator import router as operator_router
from app.web.routes_reviewer import router as reviewer_router


# Paths whose responses should NOT clear the operator's
# ``qsu_{session_id}=1`` cookie — Session Home itself + every
# ``/quick-setup/...`` endpoint (lock toggle, file submits). Everything
# else under ``/operator/`` clears the cookie so navigating away from
# Home and returning relocks the Quick Setup card.
_QUICK_SETUP_KEEP_COOKIE_RE = re.compile(
    r"^/operator/sessions/\d+(?:/quick-setup(?:/.*)?)?/?$"
)
_QUICK_SETUP_COOKIE_RE = re.compile(r"^qsu_(\d+)$")


def create_app() -> FastAPI:
    app = FastAPI(title="Review Robin Web")
    app.include_router(health_router)
    app.include_router(about_router)
    app.include_router(auth_router)
    app.include_router(operator_router)
    app.include_router(reviewer_router)

    @app.middleware("http")
    async def reset_quick_setup_unlock_on_navigation(
        request: Request, call_next
    ):
        response = await call_next(request)
        path = request.url.path
        if not path.startswith("/operator/"):
            return response
        if _QUICK_SETUP_KEEP_COOKIE_RE.match(path):
            return response
        # Operator navigated away from Session Home (and away from
        # the Quick Setup endpoints that own the cookie's
        # lifecycle). Expire any ``qsu_{session_id}`` cookies the
        # request carried so coming back to Home renders the card
        # locked.
        for cookie_name in list(request.cookies.keys()):
            m = _QUICK_SETUP_COOKIE_RE.match(cookie_name)
            if m is None:
                continue
            sid = m.group(1)
            response.delete_cookie(
                key=cookie_name, path=f"/operator/sessions/{sid}"
            )
        return response

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
