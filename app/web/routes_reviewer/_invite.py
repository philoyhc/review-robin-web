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
from app.services.email_identity import normalize_email
from app.web import views
from app.web.deps import get_or_create_user, request_correlation_id
from app.web.routes_reviewer._shared import (
    _templates,
)

router = APIRouter(prefix="/me")


@router.get("/invite/{token}", name="reviewer_invite", response_class=HTMLResponse)
def reviewer_invite(
    request: Request,
    token: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """Token landing page (Easy Auth required).

    Looks up the invitation by sha256(token); 404 if unknown or if its
    reviewer is inactive (``lookup_invitation_by_token``). If the
    signed-in user's email matches the invitation's reviewer email
    (case-insensitive), stamps ``opened_at`` on first hit and 303s to
    the reviewer surface for that session. Mismatched email returns 403
    with a dedicated page.
    """
    found = invitations_service.lookup_invitation_by_token(db, token)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            # Invitations don't expire: a fresh send or a Regenerate
            # rotates the token and kills earlier emails' links (a
            # reminder reuses the current one unless it has to fall back
            # to a fresh invitation). Participant audit M12, author's
            # ruling 2026-10-15.
            detail=(
                "This invitation link has been replaced by a newer one or "
                "is no longer valid. Use the link in your most recent "
                "email, or go to your reviews."
            ),
        )
    invitation, review_session, reviewer = found
    if normalize_email(user.email) != normalize_email(reviewer.email):
        return _templates.TemplateResponse(
            request,
            "reviewer/invite_mismatch.html",
            {
                "user": user,
                "session": review_session,
                # Partly masked (participant audit M9).
                "invited_address": views.masked_email(reviewer.email),
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
        url=f"/me/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
