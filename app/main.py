import re

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.web.deps import OperatorAllowlistDenied
from app.web.routes_about import router as about_router
from app.web.routes_auth import router as auth_router
from app.web.routes_health import router as health_router
from app.web.routes_operator import router as operator_router
from app.web.routes_reviewer import router as reviewer_router


# Paths whose responses should NOT clear the operator's
# ``qsu_{session_id}=1`` cookie — Session Home itself + every
# ``/quick-setup/...`` endpoint (lock toggle, file submits). Every
# other path clears the cookie so navigating away from Home (whether
# to another operator page like ``/operator/settings``, the sessions
# lobby ``/operator/sessions``, or ``/about``) and returning relocks
# the Quick Setup card.
#
# The ``qsu_`` literal in ``_QUICK_SETUP_COOKIE_RE`` mirrors
# ``_QUICK_SETUP_COOKIE_PREFIX`` in
# ``app/web/routes_operator/_shared.py``. If you rename the cookie
# prefix in either file, update the other.
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

    @app.exception_handler(OperatorAllowlistDenied)
    async def _operator_allowlist_denied(
        request: Request, exc: OperatorAllowlistDenied
    ) -> RedirectResponse:
        return RedirectResponse(url="/request-access", status_code=303)

    @app.middleware("http")
    async def reset_quick_setup_unlock_on_navigation(
        request: Request, call_next
    ):
        response = await call_next(request)
        path = request.url.path
        if _QUICK_SETUP_KEEP_COOKIE_RE.match(path):
            return response
        # Operator navigated away from Session Home (and away from
        # the Quick Setup endpoints that own the cookie's
        # lifecycle). Expire any ``qsu_{session_id}`` cookies the
        # request carried so coming back to Home renders the card
        # locked. The cookie is set with path ``/`` (see
        # ``app/web/routes_operator/_quick_setup.py``) so the same
        # path here matches the browser's stored cookie.
        for cookie_name in list(request.cookies.keys()):
            if _QUICK_SETUP_COOKIE_RE.match(cookie_name) is None:
                continue
            response.delete_cookie(key=cookie_name, path="/")
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
