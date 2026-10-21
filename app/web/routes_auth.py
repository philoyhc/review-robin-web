from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.identity import (
    AuthenticatedUser,
    extract_claims,
    get_current_user,
)
from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.logging_config import get_logger
from app.web.deps import find_user
from app.web import views
from app.web.return_to import resolve_return_to

log = get_logger(__name__)

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


@router.get("/auth/me")
def me(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, object]:
    return {
        "principal_id": user.principal_id,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "is_fake": user.is_fake,
    }


@router.get("/auth/me/debug", response_class=HTMLResponse)
def me_debug(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # Looked up, never created, and a changed email is not moved onto
    # the row (findings P5): this page has to render for an identity
    # ``get_or_create_user`` would refuse (no email claim). The back
    # link needs the row to name a session or to pick its fallback (the
    # lobby or /me), and a failed lookup reads as no row, so a database
    # that refuses connections does not take down the page where a
    # broken sign-in is diagnosed. A session-path ``return_to`` still
    # needs the database to look the session up.
    looked_up: list[User | None] = []

    def viewer() -> User | None:
        # Once per request: the back link and the top bar both ask.
        if not looked_up:
            try:
                looked_up.append(find_user(db, user, move_email=False))
            except SQLAlchemyError:
                # Logged: this page is where a broken sign-in is diagnosed.
                log.warning("user lookup failed", exc_info=True)
                db.rollback()
                looked_up.append(None)
        return looked_up[0]

    return_to = resolve_return_to(
        request.query_params.get("return_to"), db, viewer=viewer, routes=request.app.routes
    )
    return _templates.TemplateResponse(
        request,
        "me_debug.html",
        {
            "user": user,
            "claims": extract_claims(request),
            "return_to_url": return_to.url,
            "return_to_label": return_to.label,
            # Participant audit M8: a participant gets the participant
            # top bar here, as on their own pages.
            "participant_chrome": views.uses_participant_chrome(viewer()),
        },
    )

# ``GET /request-access`` retired in 18R Item 6. A non-operator/non-sys-admin
# who wanders to an operator page is now bounced to ``/me`` (the operator-denied
# handler in ``app/main.py``); the "how do I get access" messaging moved to
# ``/about``.
