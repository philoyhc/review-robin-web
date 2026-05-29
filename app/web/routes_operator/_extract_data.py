"""Extract data — Operations-strip tab for fine-grained shaping
of response data for offline analysis (per ``guide/extract_data.md``).

Ships as a skeleton in this PR: the page renders with the
Operations chrome and three placeholder lens sections
(By instrument / By reviewer / By reviewee). Wiring per-lens
downloads is the follow-up.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.db.session import get_db
from app.web import breadcrumbs, views
from app.web.deps import get_or_create_user, require_session_operator
from app.web.routes_operator._shared import _templates

router = APIRouter()


@router.get(
    "/sessions/{session_id}/extract-data", response_class=HTMLResponse
)
def session_extract_data(
    request: Request,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: str | None = None,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="extract-data",
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
    )
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_extract_data.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Extract data"
            ),
            "instruments": instruments,
            **workflow_ctx,
        },
    )
