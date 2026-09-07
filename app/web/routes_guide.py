"""The `/guide` page — in-app operator and participant documentation.

**Canonical operator documentation since Segment 19E rung 2.** The
material moved in from `docs/quickstart.md`, which retired to
`docs/archive/quickstart.md`; corrections belong in the template, not
there.

Which sections a viewer sees comes from `app.web.views._guide`, whose
resolver reads the viewer's operator flag and their disclosable roster
roles across every session (19E rung 7, narrowed by 19F PR 3). A viewer
who resolves **no** audiences is redirected to `/about` — see decision 6
in `guide/segment_19F_reviewee_participation_disclosure.md`.

Sits beside `/about` in the chrome link row and takes the same
``?return_to=`` treatment: `/about` is identity and access — what this
software is, who to contact — and `/guide` is how to run a session.
Neither absorbs the other.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.web.deps import get_or_create_user
from app.web.return_to import resolve_return_to
from app.web.views._guide import visible_audiences, visible_sections

router = APIRouter()

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/guide", response_class=HTMLResponse)
def guide(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    # Annotated ``Response`` rather than the union of the two it can
    # actually return: FastAPI builds a response model from the return
    # annotation, and a ``X | Y`` of two response classes is not a valid
    # Pydantic field. ``response_class=HTMLResponse`` above still sets
    # the documented default for the rendering path.
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
    # 19F PR 3 — a viewer who resolves no audiences has no Guide to
    # read, and is sent to the page that answers the question they
    # actually have. `/about` has been the app's "signed in but no
    # access" landing since 18R Item 6 retired `/request-access`: it
    # carries the app description plus the identity + operator-contact
    # note. The bounce mirrors `require_operator`'s
    # `OperatorAllowlistDenied` -> 303 to `/me`.
    #
    # A redirect rather than a 404 because the chrome offers this link
    # to everyone; refusing a link the app itself just rendered is a
    # worse answer than moving the reader somewhere useful. `base.html`
    # additionally stops rendering the link for such a viewer, so the
    # bounce is the safety net rather than the normal path.
    if not visible_audiences(db, user):
        return RedirectResponse(
            url="/about", status_code=status.HTTP_303_SEE_OTHER
        )
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
