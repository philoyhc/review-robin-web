"""The `/guide` page — in-app operator and participant documentation.

**Canonical operator documentation since Segment 19E rung 2.** The
material moved in from `docs/quickstart.md`, which retired to
`docs/archive/quickstart.md`; corrections belong in the template, not
there.

Which sections a viewer sees comes from `app.web.views._guide`. That
filter runs, but its resolver returns every audience for every viewer
until rung 7 — see that module for why the seam is live before it
narrows anything.

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

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.web.return_to import resolve_return_to
from app.web.views._guide import visible_sections

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/guide", response_class=HTMLResponse)
def guide(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # Takes the real user for the same reason `/about` does: a signed-in
    # stranger with no role should still see the chrome's identity and
    # Sign out. Which sections that user is shown comes from
    # `app.web.views._guide`, whose resolver returns every audience until
    # 19E rung 7 — the filter runs, it just does not narrow anything yet.
    return_to = resolve_return_to(request.query_params.get("return_to"), db)
    return _templates.TemplateResponse(
        request,
        "guide.html",
        {
            "user": user,
            "breadcrumbs": [],
            "return_to_url": return_to.url,
            "return_to_label": return_to.label,
            "visible_sections": visible_sections(user),
        },
    )
