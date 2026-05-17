"""Reviewer dashboard — the "My Reviews" landing page listing
every session the signed-in user is an active reviewer on.

Carved out of the single-file ``routes_reviewer.py`` in Segment
17B PR 1.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import date_formatting
from app.services import responses as responses_service
from app.services import sessions as sessions_service
from app.web import breadcrumbs
from app.web.deps import get_or_create_user
from app.web.routes_reviewer._shared import _templates

router = APIRouter(prefix="/reviewer")


@dataclass(frozen=True)
class DashboardInstrumentRow:
    """One per-instrument sub-row on the reviewer dashboard
    (Segment 15B Slice 6).

    Suppressed entirely when the session has only one instrument
    so the single-instrument dashboard stays byte-identical to its
    pre-15B render.

    Fields:

    - ``label`` — display name (``instrument.short_label`` when
      set, ``instrument.name`` otherwise).
    - ``position`` — 1-based position in the reviewer surface URL
      shape (``/reviewer/sessions/{id}/{position}``). Indexed by
      ``Instrument.order, Instrument.id`` so it matches the
      reviewer surface's own page-button ordering.
    - ``state`` — ``"not started"`` / ``"in progress"`` /
      ``"submitted"`` / ``"no assignments"``. Last value covers
      the case where the pinned rule excluded this reviewer from
      this particular instrument (multi-instrument sessions can
      have per-instrument pin gaps).
    - ``completed_rows`` / ``total_assignments`` — surfaced in the
      muted ``(N/M)`` suffix alongside the pill, same shape as
      the per-session pill row.
    """

    label: str
    position: int
    state: str
    completed_rows: int
    total_assignments: int


def _build_dashboard_instrument_rows(
    db: Session, reviewer: Reviewer, review_session: ReviewSession
) -> list[DashboardInstrumentRow]:
    """Return one :class:`DashboardInstrumentRow` per session
    instrument when ``N > 1``; empty list otherwise.

    The empty-list-on-N==1 contract keeps the single-instrument
    dashboard byte-identical (invariant #3 from the segment plan).
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    if len(instruments) <= 1:
        return []
    state_by_instrument = (
        responses_service.reviewer_session_state_per_instrument(
            db, reviewer=reviewer, session_id=review_session.id
        )
    )
    rows: list[DashboardInstrumentRow] = []
    for position, instrument in enumerate(instruments, start=1):
        state = state_by_instrument.get(instrument.id)
        if state is None:
            rows.append(
                DashboardInstrumentRow(
                    label=instrument.short_label or instrument.name,
                    position=position,
                    state="no assignments",
                    completed_rows=0,
                    total_assignments=0,
                )
            )
            continue
        rows.append(
            DashboardInstrumentRow(
                label=instrument.short_label or instrument.name,
                position=position,
                state=state.pill_state,
                completed_rows=state.completed_count,
                total_assignments=state.total_assignments,
            )
        )
    return rows


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
        session_zone = sessions_service.resolve_session_timezone(review_session)
        items.append(
            {
                "reviewer": reviewer,
                "session": review_session,
                "pill": pill,
                "deadline_text": date_formatting.format_datetime(
                    review_session.deadline, session_zone
                ),
                "deadline_timezone_label": date_formatting.gmt_offset_zone_label(
                    session_zone, at=review_session.deadline
                ),
                "instrument_rows": _build_dashboard_instrument_rows(
                    db, reviewer, review_session
                ),
            }
        )
    return _templates.TemplateResponse(
        request,
        "reviewer/dashboard.html",
        {
            "user": user,
            "items": items,
            "reviewer_review_count": len(items),
            "breadcrumbs": breadcrumbs.reviewer_root(),
        },
    )
