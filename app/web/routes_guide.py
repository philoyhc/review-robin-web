"""The `/guide` page — in-app operator and participant documentation.

**Canonical operator documentation since Segment 19E rung 2.** The
material moved in from `docs/quickstart.md`, which retired to
`docs/archive/quickstart.md`; corrections belong in the template, not
there.

Which sections a viewer sees comes from `app.web.views._guide`, whose
resolver reads the viewer's operator flag and their roster rows across
every session (19E rung 7). A viewer holding no role sees the whole
Guide — see that module for why.

Sits beside `/about` in the chrome link row and takes the same
``?return_to=`` treatment: `/about` is identity and access — what this
software is, who to contact — and `/guide` is how to run a session.
Neither absorbs the other.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.web.deps import get_or_create_user
from app.web.return_to import resolve_return_to
from app.web.views._guide import visible_sections

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/guide", response_class=HTMLResponse)
def guide(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # Depends on the persisted `User` row, not the `AuthenticatedUser`
    # from the headers, because rung 7's resolver reads `is_operator` and
    # that lives on the row. `get_or_create_user` still admits a
    # signed-in stranger with no role — it creates their row like every
    # other page does — so the page stays reachable by anyone signed in,
    # which is the property the previous dependency was chosen for.
    #
    # Side effect worth naming: the chrome's "Signed in as …" reads
    # `user.display_label`, which `AuthenticatedUser` does not have, so
    # this page has been rendering that line with an empty name since it
    # shipped. Switching the dependency fixes it.
    return_to = resolve_return_to(request.query_params.get("return_to"), db)
    return _templates.TemplateResponse(
        request,
        "guide.html",
        {
            "user": user,
            "breadcrumbs": [],
            "return_to_url": return_to.url,
            "return_to_label": return_to.label,
            "visible_sections": visible_sections(db, user),
        },
    )
