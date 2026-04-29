from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import invitations as invitations_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_reviewer_in_session,
)

router = APIRouter(prefix="/reviewer", tags=["reviewer"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


@router.get("", response_class=HTMLResponse)
def reviewer_dashboard(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user_email = (user.email or "").casefold()
    rows = list(
        db.execute(
            select(Reviewer, ReviewSession)
            .join(ReviewSession, ReviewSession.id == Reviewer.session_id)
            .where(Reviewer.status == "active")
            .order_by(ReviewSession.updated_at.desc())
        ).all()
    )
    items = []
    for reviewer, review_session in rows:
        if reviewer.email.casefold() != user_email:
            continue
        pill = responses_service.session_pill_for_reviewer(
            db, reviewer=reviewer, session_id=review_session.id
        )
        items.append(
            {
                "reviewer": reviewer,
                "session": review_session,
                "pill": pill,
            }
        )
    return _templates.TemplateResponse(
        request,
        "reviewer/dashboard.html",
        {
            "user": user,
            "items": items,
            "breadcrumbs": breadcrumbs.reviewer_root(),
        },
    )


def _load_assignments_with_relations(
    db: Session, *, session_id: int, reviewer_id: int
) -> list[Assignment]:
    stmt = (
        select(Assignment)
        .options(
            joinedload(Assignment.reviewee),
            joinedload(Assignment.instrument),
        )
        .where(
            Assignment.session_id == session_id,
            Assignment.reviewer_id == reviewer_id,
            Assignment.include.is_(True),
        )
        .order_by(Assignment.id)
    )
    return list(db.execute(stmt).scalars())


def _instruments_for_session(db: Session, session_id: int) -> dict[int, Instrument]:
    rows = db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalars()
    return {i.id: i for i in rows}


def _require_session_accepting(
    db: Session, review_session: ReviewSession, reviewer: Reviewer
) -> None:
    """Raise 403 unless every instrument the reviewer would write to is accepting."""
    lifecycle.observe_deadline(db, review_session)
    db.refresh(review_session)
    assignments = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id,
            Assignment.reviewer_id == reviewer.id,
            Assignment.include.is_(True),
        )
    ).scalars()
    instrument_ids = {a.instrument_id for a in assignments}
    if not instrument_ids:
        # No assignments — nothing to write. Treat as not accepting so the
        # reviewer surface flow is consistent.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No longer accepting responses",
        )
    instruments = _instruments_for_session(db, review_session.id)
    for instrument_id in instrument_ids:
        instrument = instruments.get(instrument_id)
        if instrument is None or not lifecycle.session_accepts_responses(
            review_session, instrument
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No longer accepting responses",
            )


def _surface_context(
    *,
    db: Session,
    user: User,
    reviewer: Reviewer,
    review_session: ReviewSession,
    saved: bool,
    submitted: bool,
    missing: list[responses_service.MissingPosition] | None = None,
    show_acknowledge: bool = False,
) -> dict:
    lifecycle.observe_deadline(db, review_session)
    db.refresh(review_session)
    assignments = _load_assignments_with_relations(
        db, session_id=review_session.id, reviewer_id=reviewer.id
    )
    instrument_ids = {a.instrument_id for a in assignments}
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    if instrument_ids:
        stmt = (
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id.in_(instrument_ids))
            .order_by(InstrumentResponseField.order)
        )
        for field in db.execute(stmt).scalars():
            fields_by_instrument.setdefault(field.instrument_id, []).append(field)

    response_rows: dict[tuple[int, int], Response] = {}
    if assignments:
        stmt = select(Response).where(
            Response.assignment_id.in_([a.id for a in assignments])
        )
        for r in db.execute(stmt).scalars():
            response_rows[(r.assignment_id, r.response_field_id)] = r

    instruments = _instruments_for_session(db, review_session.id)

    rows = []
    any_accepting = False
    any_closed_with_hidden_values = False
    for assignment in assignments:
        fields = fields_by_instrument.get(assignment.instrument_id, [])
        instrument = instruments.get(assignment.instrument_id)
        accepting = bool(
            instrument
            and lifecycle.session_accepts_responses(review_session, instrument)
        )
        if accepting:
            any_accepting = True
        show_values = accepting or (
            instrument is not None and instrument.responses_visible_when_closed
        )
        if not show_values:
            any_closed_with_hidden_values = True
        cells = []
        for field in fields:
            existing = response_rows.get((assignment.id, field.id))
            value = (existing.value or "") if existing else ""
            cells.append(
                {
                    "field": field,
                    "value": value if show_values else "",
                }
            )
        is_complete, missing_count, latest_submitted = (
            responses_service.compute_row_completion(db, assignment)
        )
        pair_contexts = []
        ctx = assignment.context or {}
        for slot in (1, 2, 3):
            value = ctx.get(f"pair_context_{slot}")
            if value:
                pair_contexts.append((slot, value))
        rows.append(
            {
                "assignment": assignment,
                "cells": cells,
                "is_complete": is_complete,
                "missing_count": missing_count,
                "submitted_at": latest_submitted,
                "pair_contexts": pair_contexts,
                "accepting": accepting,
                "show_values": show_values,
            }
        )

    return {
        "user": user,
        "session": review_session,
        "reviewer": reviewer,
        "rows": rows,
        "saved": saved,
        "submitted": submitted,
        "missing": missing or [],
        "show_acknowledge": show_acknowledge,
        "any_required": any(
            any(f.required for f in fields_by_instrument.get(a.instrument_id, []))
            for a in assignments
        ),
        "any_accepting": any_accepting,
        "any_closed_with_hidden_values": any_closed_with_hidden_values,
    }


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def review_surface(
    request: Request,
    saved: str | None = None,
    submitted: str | None = None,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    reviewer, review_session = reviewer_session
    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        saved=saved == "ok",
        submitted=submitted == "ok",
    )
    context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
    return _templates.TemplateResponse(
        request, "reviewer/review_surface.html", context
    )


@router.post(
    "/sessions/{session_id}/save",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_save(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    upserts = responses_service.parse_form_payload(
        {k: v for k, v in form.items() if isinstance(v, str)}
    )
    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}?saved=ok",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/submit",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_submit(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    string_form = {k: v for k, v in form.items() if isinstance(v, str)}
    acknowledge = string_form.get("acknowledge_missing") == "true"
    upserts = responses_service.parse_form_payload(string_form)
    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        acknowledge_missing=acknowledge,
        correlation_id=request_correlation_id(),
    )
    if not result.submitted:
        context = _surface_context(
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            saved=False,
            submitted=False,
            missing=result.missing,
            show_acknowledge=True,
        )
        context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
        return _templates.TemplateResponse(
            request,
            "reviewer/review_surface.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}?submitted=ok",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/clear",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewer_clear(
    confirm: str | None = Form(default=None),
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    responses_service.clear_all(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    invitation, review_session, reviewer = found
    if (user.email or "").casefold() != reviewer.email.casefold():
        return _templates.TemplateResponse(
            request,
            "reviewer/invite_mismatch.html",
            {
                "user": user,
                "session": review_session,
                "reviewer_email": reviewer.email,
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
