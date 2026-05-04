from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, not_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import instruments as instruments_service
from app.services import invitations as invitations_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_reviewer_in_session,
)

router = APIRouter(prefix="/reviewer", tags=["reviewer"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version


def reviewer_review_count_for_user(db: Session, user: User) -> int:
    """Count active Reviewer rows whose email matches ``user``, case-insensitive.

    Drives the conditional "My Reviews" link in the reviewer chrome
    (suppressed when the user has only a single review — the dashboard
    isn't useful as a navigation hub in that case).
    """
    target = (user.email or "").casefold()
    if not target:
        return 0
    rows = db.execute(
        select(Reviewer).where(Reviewer.status == "active")
    ).scalars()
    return sum(1 for r in rows if r.email.casefold() == target)


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
            "reviewer_review_count": len(items),
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


_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD = not_(
    and_(
        InstrumentDisplayField.source_type == "reviewee",
        InstrumentDisplayField.source_field.in_(["name", "email_or_identifier"]),
    )
)
"""Filter expression: exclude display fields that duplicate the always-rendered
Reviewee identity column (name + email). The operator can still configure these
on the Instruments page; they're just not rendered as separate columns on the
reviewer surface since the Reviewee column already shows both."""


def _instruments_for_session(db: Session, session_id: int) -> dict[int, Instrument]:
    rows = db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalars()
    return {i.id: i for i in rows}


def _require_session_accepting(
    db: Session, review_session: ReviewSession, reviewer: Reviewer
) -> None:
    """Raise 403 unless every instrument the reviewer would write to is accepting."""
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
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
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
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

    display_fields_by_instrument: dict[int, list[InstrumentDisplayField]] = {}
    if instrument_ids:
        stmt = (
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id.in_(instrument_ids))
            .where(InstrumentDisplayField.visible.is_(True))
            .where(_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD)
            .order_by(InstrumentDisplayField.order, InstrumentDisplayField.id)
        )
        for field in db.execute(stmt).scalars():
            display_fields_by_instrument.setdefault(field.instrument_id, []).append(field)

    response_rows: dict[tuple[int, int], Response] = {}
    if assignments:
        stmt = select(Response).where(
            Response.assignment_id.in_([a.id for a in assignments])
        )
        for r in db.execute(stmt).scalars():
            response_rows[(r.assignment_id, r.response_field_id)] = r

    instruments = _instruments_for_session(db, review_session.id)

    rows_by_instrument: dict[int, list[dict]] = {}
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
        display_cells = []
        for display_field in display_fields_by_instrument.get(
            assignment.instrument_id, []
        ):
            display_cells.append(
                {
                    "field": display_field,
                    "label": instruments_service.display_field_label(display_field),
                    "value": instruments_service.display_field_value(
                        display_field, assignment
                    ),
                    "is_profile_link": (
                        display_field.source_type == "reviewee"
                        and display_field.source_field == "profile_link"
                    ),
                }
            )
        rows_by_instrument.setdefault(assignment.instrument_id, []).append(
            {
                "assignment": assignment,
                "cells": cells,
                "is_complete": is_complete,
                "missing_count": missing_count,
                "submitted_at": latest_submitted,
                "display_cells": display_cells,
                "accepting": accepting,
                "show_values": show_values,
            }
        )

    instrument_groups = []
    flat_rows = []
    position_by_id = {
        inst.id: idx
        for idx, inst in enumerate(
            sorted(instruments.values(), key=lambda i: (i.order, i.id)),
            start=1,
        )
    }
    total_instrument_count = len(instruments)
    for instrument_id, group_rows in rows_by_instrument.items():
        instrument = instruments.get(instrument_id)
        if instrument is None:
            continue
        fields = fields_by_instrument.get(instrument_id, [])
        help_block_items = [
            f for f in fields if f.help_text and f.help_text_visible
        ]
        heading = views.reviewer_instrument_heading(
            description=instrument.description,
            position=position_by_id[instrument_id],
            total_count=total_instrument_count,
        )
        display_fields = display_fields_by_instrument.get(instrument_id, [])
        display_field_headers = [
            {
                "field": df,
                "label": instruments_service.display_field_label(df),
                "is_profile_link": (
                    df.source_type == "reviewee"
                    and df.source_field == "profile_link"
                ),
            }
            for df in display_fields
        ]
        instrument_groups.append(
            {
                "instrument": instrument,
                "heading": heading,
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "show_status_col": show_acknowledge
                or any(r.get("submitted_at") for r in group_rows),
            }
        )
        flat_rows.extend(group_rows)

    return {
        "user": user,
        "session": review_session,
        "reviewer": reviewer,
        "instrument_groups": instrument_groups,
        "rows": flat_rows,
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


# ---------------------------------------------------------------------------
# Operator preview surface (Segment 10B-3)
# ---------------------------------------------------------------------------

# Sample placeholder values per display-field source. Used to fill cells on
# synthetic preview rows when the session has fewer than three real
# assignments. Keys cover the seven D6 sources; pair_context.* and
# reviewee.tag_* share copy-text per the segment plan.
_SYNTHETIC_VALUES_BY_SOURCE: dict[tuple[str, str], str] = {
    ("reviewee", "name"): "",  # rendered in the dedicated Reviewee cell
    ("reviewee", "email_or_identifier"): "",
    ("reviewee", "tag_1"): "Sample tag value",
    ("reviewee", "tag_2"): "Sample tag value",
    ("reviewee", "tag_3"): "Sample tag value",
    ("reviewee", "profile_link"): "https://example.edu/sample-profile",
    ("pair_context", "1"): "Sample pair context",
    ("pair_context", "2"): "Sample pair context",
    ("pair_context", "3"): "Sample pair context",
}


def _make_synthetic_row(
    *,
    instrument: Instrument,
    index: int,
    response_fields: list[InstrumentResponseField],
    display_fields: list[InstrumentDisplayField],
) -> dict:
    """Build a row dict with the same shape as ``_surface_context`` for a
    synthetic (placeholder) reviewee. Used by ``build_preview_context`` to
    pad up to three rows when a session has fewer real assignments.

    Synthetic rows expose only the attributes the reviewer-surface template
    actually reads:

    - ``assignment.id`` (negative to avoid colliding with real autoincrement
      ids; the form wrapper is suppressed in preview, so this id never gets
      submitted).
    - ``assignment.reviewee.name`` and ``email_or_identifier``.

    A future template edit referencing a new attribute on the synthetic
    namespace would silently AttributeError; the unit tests guard the
    currently-exposed shape.
    """
    reviewee = SimpleNamespace(
        name=f"Sample Reviewee {index + 1}",
        email_or_identifier=f"sample{index + 1}@example.edu",
    )
    assignment = SimpleNamespace(
        id=-(index + 1),
        reviewee=reviewee,
    )
    display_cells = [
        {
            "field": df,
            "label": instruments_service.display_field_label(df),
            "value": _SYNTHETIC_VALUES_BY_SOURCE.get(
                (df.source_type, df.source_field)
            ),
            "is_profile_link": (
                df.source_type == "reviewee"
                and df.source_field == "profile_link"
            ),
        }
        for df in display_fields
    ]
    cells = [{"field": field, "value": ""} for field in response_fields]
    return {
        "assignment": assignment,
        "cells": cells,
        "is_complete": False,
        "missing_count": 0,
        "submitted_at": None,
        "display_cells": display_cells,
        "accepting": False,
        "show_values": True,
    }


def build_preview_context(
    *,
    db: Session,
    user: User,
    review_session: ReviewSession,
) -> dict:
    """Operator-side mirror of :func:`_surface_context`.

    Builds the reviewer-surface view shape with up to three rows: real
    assignments first (by ``Assignment.id`` ascending, no reviewer-id
    filter), padded with synthetic placeholders to reach three. Per
    Segment 10B-3 D9 this is read-only — it does **not** call
    ``lifecycle.observe_deadline`` (which mutates the DB on a deadline
    crossing) and forces ``accepting=False`` on every row so the existing
    template's ``disabled_attr`` branch renders every input disabled.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    if not instruments:
        return {
            "user": user,
            "session": review_session,
            "reviewer": None,
            "instrument_groups": [],
            "rows": [],
            "saved": False,
            "submitted": False,
            "missing": [],
            "show_acknowledge": False,
            "any_required": False,
            "any_accepting": False,
            "any_closed_with_hidden_values": False,
            "preview_mode": True,
        }

    instrument_ids = [i.id for i in instruments]
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    stmt = (
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id.in_(instrument_ids))
        .order_by(InstrumentResponseField.order)
    )
    for field in db.execute(stmt).scalars():
        fields_by_instrument.setdefault(field.instrument_id, []).append(field)

    display_fields_by_instrument: dict[int, list[InstrumentDisplayField]] = {}
    stmt = (
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id.in_(instrument_ids))
        .where(InstrumentDisplayField.visible.is_(True))
        .where(_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD)
        .order_by(InstrumentDisplayField.order, InstrumentDisplayField.id)
    )
    for field in db.execute(stmt).scalars():
        display_fields_by_instrument.setdefault(field.instrument_id, []).append(
            field
        )

    real_assignments = list(
        db.execute(
            select(Assignment)
            .options(
                joinedload(Assignment.reviewee),
                joinedload(Assignment.instrument),
            )
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
            )
            .order_by(Assignment.id)
            .limit(3)
        ).scalars()
    )

    rows_by_instrument: dict[int, list[dict]] = {}
    for assignment in real_assignments:
        fields = fields_by_instrument.get(assignment.instrument_id, [])
        display_fields = display_fields_by_instrument.get(
            assignment.instrument_id, []
        )
        cells = [{"field": field, "value": ""} for field in fields]
        display_cells = [
            {
                "field": df,
                "label": instruments_service.display_field_label(df),
                "value": instruments_service.display_field_value(df, assignment),
                "is_profile_link": (
                    df.source_type == "reviewee"
                    and df.source_field == "profile_link"
                ),
            }
            for df in display_fields
        ]
        rows_by_instrument.setdefault(assignment.instrument_id, []).append(
            {
                "assignment": assignment,
                "cells": cells,
                "is_complete": False,
                "missing_count": 0,
                "submitted_at": None,
                "display_cells": display_cells,
                "accepting": False,
                "show_values": True,
            }
        )

    # Pad with synthetic rows. Anchor synthetic rows to the first instrument
    # that has real rows. When no real assignments exist, anchor to the
    # session's first instrument.
    needed = 3 - len(real_assignments)
    if needed > 0:
        if rows_by_instrument:
            anchor_id = next(iter(rows_by_instrument))
        else:
            anchor_id = instruments[0].id
        anchor_instrument = next(i for i in instruments if i.id == anchor_id)
        anchor_response_fields = fields_by_instrument.get(anchor_id, [])
        anchor_display_fields = display_fields_by_instrument.get(anchor_id, [])
        synthetic_offset = len(real_assignments)
        for offset in range(needed):
            rows_by_instrument.setdefault(anchor_id, []).append(
                _make_synthetic_row(
                    instrument=anchor_instrument,
                    index=synthetic_offset + offset,
                    response_fields=anchor_response_fields,
                    display_fields=anchor_display_fields,
                )
            )

    instrument_groups: list[dict] = []
    flat_rows: list[dict] = []
    total_instrument_count = len(instruments)
    for position, instrument in enumerate(instruments, start=1):
        group_rows = rows_by_instrument.get(instrument.id, [])
        if not group_rows:
            continue
        fields = fields_by_instrument.get(instrument.id, [])
        help_block_items = [
            f for f in fields if f.help_text and f.help_text_visible
        ]
        heading = views.reviewer_instrument_heading(
            description=instrument.description,
            position=position,
            total_count=total_instrument_count,
        )
        display_fields = display_fields_by_instrument.get(instrument.id, [])
        display_field_headers = [
            {
                "field": df,
                "label": instruments_service.display_field_label(df),
                "is_profile_link": (
                    df.source_type == "reviewee"
                    and df.source_field == "profile_link"
                ),
            }
            for df in display_fields
        ]
        instrument_groups.append(
            {
                "instrument": instrument,
                "heading": heading,
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "show_status_col": False,
            }
        )
        flat_rows.extend(group_rows)

    return {
        "user": user,
        "session": review_session,
        "reviewer": None,
        "instrument_groups": instrument_groups,
        "rows": flat_rows,
        "saved": False,
        "submitted": False,
        "missing": [],
        "show_acknowledge": False,
        "any_required": False,
        "any_accepting": False,
        "any_closed_with_hidden_values": False,
        "preview_mode": True,
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
    context["reviewer_review_count"] = reviewer_review_count_for_user(db, user)
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
        context["reviewer_review_count"] = reviewer_review_count_for_user(
            db, user
        )
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
