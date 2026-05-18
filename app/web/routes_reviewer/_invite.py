"""Reviewer invitation-token landing route.

Carved out of the single-file ``routes_reviewer.py`` in Segment
17B PR 1.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import invitations as invitations_service
from app.web import breadcrumbs
from app.web.deps import get_or_create_user, request_correlation_id
from app.web.routes_reviewer._shared import (
    _templates,
    reviewer_review_count_for_user,
)

router = APIRouter(prefix="/reviewer")


@router.get("/invite/{token}", name="reviewer_invite", response_class=HTMLResponse)
def reviewer_invite(
    request: Request,
    token: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """Token landing page (Easy Auth required).

    Looks up the invitation by sha256(token); 404 if unknown. If the
    signed-in user's email matches the invitation's reviewer email
    (case-insensitive), stamps ``opened_at`` on first hit and 303s to
    the reviewer surface for that session. Mismatched email returns 403
    with a dedicated page.
    """
    found = invitations_service.lookup_invitation_by_token(db, token)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This invitation link is invalid or has expired.",
        )
    invitation, review_session, reviewer = found
    if (user.email or "").casefold() != reviewer.email.casefold():
        return _templates.TemplateResponse(
            request,
            "reviewer/invite_mismatch.html",
            {
                "user": user,
                "session": review_session,
                "reviewer_email": reviewer.email,
                "reviewer_review_count": reviewer_review_count_for_user(
                    db, user
                ),
                "breadcrumbs": breadcrumbs.reviewer_invite_mismatch(),
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )
    invitations_service.record_open(
        db,
        invitation=invitation,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
