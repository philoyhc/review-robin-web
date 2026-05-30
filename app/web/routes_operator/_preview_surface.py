"""Operator-side full preview of the reviewer surface (Segment 18Q).

Mirror of the reviewer's ``GET /me/sessions/{id}/{page_n}`` for
the operator: renders the same ``reviewer/review_surface.html``
template against the same ``_surface_context`` plumbing, but bypasses
the deadline / acceptance gates and rewrites the action-row Prev/Next
URLs back at this operator-side route so the operator can flip pages.
Save / Discard / Submit render as inert disabled buttons in
``preview_mode``; the surface ``<form>`` is replaced with a ``<div>``
so even pressing Enter cannot drive a write.

Distinct from the iframe-based preview card on the Previews hub
(``_operations.py`` ``previews_index``), which renders the same
template but inside a sandboxed iframe and shows synthetic placeholder
rows. The Previews hub now links here from its surface card.

The bare ``GET /sessions/{id}/preview-surface`` 303s to ``/preview-
surface/1``. Optional ``?reviewer_email=`` selects which reviewer to
preview as; when blank the route falls back to the first reviewer in
the session. When the session has zero reviewers the route 303s back
to the Previews hub, which renders the empty-state message.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.db.session import get_db
from app.web import breadcrumbs, views
from app.web.deps import get_or_create_user, require_session_operator
from app.web.routes_operator._shared import _templates
from app.web.routes_reviewer._shared import validate_page_n
from app.web.routes_reviewer._surface import _pages_for_session, _surface_context


router = APIRouter()


def _preview_url(session_id: int, page_n: int, reviewer_email: str) -> str:
    base = f"/operator/sessions/{session_id}/preview-surface/{page_n}"
    if reviewer_email:
        return f"{base}?{urlencode({'reviewer_email': reviewer_email})}"
    return base


def _resolve_preview_reviewer(
    db: Session, review_session: ReviewSession, reviewer_email: str
) -> Reviewer | None:
    """Pick the reviewer to preview as. ``?reviewer_email=`` selects;
    when blank, falls back to the first reviewer in the session
    (alphabetical-by-email, matching the picker's option order) so
    the surface still renders. An unmatched non-empty email returns
    ``None`` — caller 303s back to the Previews hub where the
    picker's "No reviewer matched" hint renders. Returns ``None``
    too when the session has zero reviewers."""
    picker = views.build_preview_picker_context(
        db, review_session, reviewer_email
    )
    if picker.current is not None:
        return db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id,
                Reviewer.id == picker.current.reviewer_id,
            )
        ).scalar_one()
    if picker.no_match_query is not None:
        return None
    if picker.options:
        first = picker.options[0]
        return db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id,
                Reviewer.id == first.reviewer_id,
            )
        ).scalar_one()
    return None


@router.get(
    "/sessions/{session_id}/preview-surface",
    response_class=HTMLResponse,
    response_model=None,
)
def preview_surface_default_page(
    session_id: int,
    reviewer_email: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Bare-URL fallback. 303s to ``/preview-surface/1`` preserving the
    optional reviewer-email picker."""
    return RedirectResponse(
        url=_preview_url(review_session.id, 1, reviewer_email),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/sessions/{session_id}/preview-surface/{page_n}",
    response_class=HTMLResponse,
    response_model=None,
)
def preview_surface(
    request: Request,
    page_n: int,
    reviewer_email: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    reviewer = _resolve_preview_reviewer(db, review_session, reviewer_email)
    if reviewer is None:
        previews_url = f"/operator/sessions/{review_session.id}/previews"
        if reviewer_email:
            previews_url = (
                f"{previews_url}?{urlencode({'reviewer_email': reviewer_email})}"
            )
        return RedirectResponse(
            url=previews_url,
            status_code=status.HTTP_303_SEE_OTHER,
        )

    pages = _pages_for_session(db, review_session.id)
    validate_page_n(page_n, pages)

    def page_url(n: int) -> str:
        return _preview_url(review_session.id, n, reviewer_email)

    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        page_n=page_n,
        cookies=dict(request.cookies),
        preview_mode=True,
        page_url_builder=page_url,
    )
    context["breadcrumbs"] = breadcrumbs.operator_session_child(
        review_session, "Preview reviewer surface"
    )
    return _templates.TemplateResponse(
        request, "reviewer/review_surface.html", context
    )
