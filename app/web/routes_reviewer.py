from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


PageStatusState = Literal["not_started", "in_progress", "complete", "submitted"]


@dataclass(frozen=True)
class PageStatus:
    """Per-page completion status for the right-half status panel.

    Lands in template context as ``page_statuses: list[PageStatus]``,
    one entry per instrument the reviewer has assignments on. Single-
    instrument sessions still get one entry — the panel always
    renders. Operator preview passes an empty list (per-page state
    is moot for synthetic preview rows).
    """

    position: int
    label: str  # bare "Page N" — short labels live on Page buttons (PR γ)
    state: PageStatusState


def _page_status_for_group(group_rows: list[dict]) -> PageStatusState:
    """Roll up per-row completion data into a single page state.

    Order of evaluation matches the spec table in
    ``spec/reviewer-surface.md`` "Per-page status":

    1. ``submitted`` — every row has ``submitted_at`` set. Submit is
       a hard gate on missing-required, so ``submitted`` implies
       ``complete`` today; the two states are kept separate so a
       future operator-side ``required`` change after submit
       doesn't silently demote the row from ``submitted``.
    2. ``complete`` — every required field on every row has a saved
       value (``is_complete``).
    3. ``in_progress`` — at least one row carries Response data,
       but neither ``submitted`` nor ``complete`` apply.
    4. ``not_started`` — no Response data on any row.

    ``in_progress`` falls back to "any row has at least one cell
    with a non-empty value" — a Response row can exist with an
    empty string, but that's the same shape as "not started" for
    pill-display purposes.
    """
    if not group_rows:
        return "not_started"
    if all(r.get("submitted_at") for r in group_rows):
        return "submitted"
    if all(r.get("is_complete") for r in group_rows):
        return "complete"
    has_any_value = any(
        any((cell.get("value") or "") for cell in r.get("cells", []))
        for r in group_rows
    )
    return "in_progress" if has_any_value else "not_started"


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
    current_position: int,
    missing: list[responses_service.MissingPosition] | None = None,
    errors: list[responses_service.ValidationError] | None = None,
    bad_values: dict[tuple[int, str], str] | None = None,
    show_incomplete_marks: bool = False,
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
            # On a re-render after server-side validation, the user's
            # typed-but-invalid value (which never reached the DB) wins
            # so they can correct it in place.
            if bad_values is not None:
                override = bad_values.get((assignment.id, field.field_key))
                if override is not None:
                    value = override
            cells.append(
                {
                    "field": field,
                    "value": value if show_values else "",
                    "placeholder": views.placeholder_for_field(field),
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
        heading = views.instrument_heading(
            instrument=instrument,
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
                "position": position_by_id[instrument_id],
                "is_current": position_by_id[instrument_id] == current_position,
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "show_status_col": show_incomplete_marks
                or any(r.get("submitted_at") for r in group_rows),
            }
        )
        flat_rows.extend(group_rows)

    # Per-page status pills for the right-half status panel (PR β).
    # One entry per instrument the reviewer has assignments on, sorted
    # by URL position so the panel reads top-to-bottom in the same
    # order the Page buttons land in.
    page_statuses: list[PageStatus] = []
    instrument_groups_by_id = {
        g["instrument"].id: g for g in instrument_groups
    }
    for inst in sorted(instruments.values(), key=lambda i: (i.order, i.id)):
        if inst.id not in instrument_groups_by_id:
            continue
        position = position_by_id[inst.id]
        page_statuses.append(
            PageStatus(
                position=position,
                label=f"Page {position}",
                state=_page_status_for_group(
                    instrument_groups_by_id[inst.id]["rows"]
                ),
            )
        )

    # Page buttons for the unified action row (PR γ). One per instrument
    # the reviewer has assignments on, sorted by session-wide position;
    # the button at ``current_position`` renders disabled.
    page_buttons: list[views.PageButton] = []
    for inst in sorted(instruments.values(), key=lambda i: (i.order, i.id)):
        if inst.id not in instrument_groups_by_id:
            continue
        position = position_by_id[inst.id]
        page_buttons.append(
            views.PageButton(
                position=position,
                label=views.page_button_label(inst, position),
                href=f"/reviewer/sessions/{review_session.id}/{position}",
                is_current=(position == current_position),
            )
        )

    # PR δ — render every instrument group the reviewer is assigned
    # on; CSS hides the non-active ones via
    # `.rs-paginated > .rs-instrument-group:not(.rs-active)`. The
    # active group (matching the URL position) carries the
    # ``rs-active`` modifier, set per ``group["is_current"]``. PR γ
    # narrowed rendering server-side so cross-page dirty edits were
    # discarded on Page click; PR δ flips that to client-side toggle
    # so dirty edits survive navigation.
    instrument_groups.sort(key=lambda g: g["position"])

    return {
        "user": user,
        "session": review_session,
        "reviewer": reviewer,
        "instrument_groups": instrument_groups,
        "rows": flat_rows,
        "missing": missing or [],
        "errors": errors or [],
        "show_incomplete_marks": show_incomplete_marks,
        "any_required": any(
            any(f.required for f in fields_by_instrument.get(a.instrument_id, []))
            for a in assignments
        ),
        "any_accepting": any_accepting,
        "any_closed_with_hidden_values": any_closed_with_hidden_values,
        "page_statuses": page_statuses,
        "page_buttons": page_buttons,
        "current_position": current_position,
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
    cells = [
        {
            "field": field,
            "value": "",
            "placeholder": views.placeholder_for_field(field),
        }
        for field in response_fields
    ]
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
            "missing": [],
            "errors": [],
            "show_incomplete_marks": False,
            "any_required": False,
            "any_accepting": False,
            "any_closed_with_hidden_values": False,
            "page_statuses": [],
            "page_buttons": [],
            "current_position": 1,
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
        cells = [
            {
                "field": field,
                "value": "",
                "placeholder": views.placeholder_for_field(field),
            }
            for field in fields
        ]
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
        heading = views.instrument_heading(
            instrument=instrument,
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
                "position": position,
                # Operator preview always treats Page #1 as the active
                # group; the synthetic surface has no client-side
                # navigation handler.
                "is_current": position == 1,
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "show_status_col": False,
            }
        )
        flat_rows.extend(group_rows)

    # Operator preview — build Page N buttons so multi-instrument
    # preview lets the operator flip between pages (per Segment 11D
    # follow-on PR ε). The unified action row collapses to Page N
    # buttons only in preview; Save / Discard / Submit / divider are
    # suppressed at the partial level.
    page_buttons: list[views.PageButton] = [
        views.PageButton(
            position=group["position"],
            label=views.page_button_label(group["instrument"], group["position"]),
            href=f"/operator/sessions/{review_session.id}/preview",
            is_current=group["is_current"],
        )
        for group in instrument_groups
    ]

    return {
        "user": user,
        "session": review_session,
        "reviewer": None,
        "instrument_groups": instrument_groups,
        "rows": flat_rows,
        "missing": [],
        "errors": [],
        "show_incomplete_marks": False,
        "any_required": False,
        "any_accepting": False,
        "any_closed_with_hidden_values": False,
        "page_statuses": [],
        "page_buttons": page_buttons,
        "current_position": 1,
        "preview_mode": True,
    }


# ─────────────────────────────────────────────────────────────────
# Reviewer surface — multi-instrument-aware URL pattern (Segment 11D
# follow-on, PR α). The surface itself still renders today's stacked
# layout; the URL gains an `{instrument_position}` segment so PRs β/γ/δ
# can layer the per-page UI on top without another URL break.
#
# - GET  /sessions/{id}                         → 303 to /sessions/{id}/1
# - GET  /sessions/{id}/{instrument_position}   → renders the surface
# - POST /sessions/{id}/{instrument_position}/save
# - POST /sessions/{id}/submit                  → session-wide
# - POST /sessions/{id}/clear                   → session-wide
#
# Submit and Clear stay session-wide; their redirect targets read a
# `current_position` hidden form field so the reviewer lands back on the
# page they were on. The position segment on Save is decorative in PR α
# (the route accepts it but doesn't filter by it) — PR γ wires the
# per-position filter alongside the rendering-narrows step.
# ─────────────────────────────────────────────────────────────────


def submit_redirect_url(review_session: ReviewSession, position: int) -> str:
    """Where to send the reviewer after a successful submit — back to
    the page they pressed Submit from. The deferred standalone-
    confirmation page can swap the URL via this helper without touching
    the surface route.
    """
    return f"/reviewer/sessions/{review_session.id}/{position}"


def _read_current_position(form: object, default: int = 1) -> int:
    """Parse a ``current_position`` hidden field from a reviewer-surface
    form POST. Falls back to ``default`` (1) when missing or malformed
    so a stray POST doesn't 500 the route. Out-of-range values still
    redirect to that position; the GET route 404s if it's truly invalid.
    """
    raw = form.get("current_position") if hasattr(form, "get") else None
    if not isinstance(raw, str):
        return default
    try:
        n = int(raw)
    except ValueError:
        return default
    return n if n >= 1 else default


@router.get("/sessions/{session_id}", response_class=HTMLResponse, response_model=None)
def review_surface_default_position(session_id: int) -> RedirectResponse:
    """Bare-URL fallback. 303s to ``/{id}/1`` so existing invitation
    links and bookmarks keep working. Auth happens on the destination
    handler — we don't 401 here because the redirect is harmless and
    skipping the dependency keeps this handler trivial.
    """
    return RedirectResponse(
        url=f"/reviewer/sessions/{session_id}/1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/sessions/{session_id}/{instrument_position}",
    response_class=HTMLResponse,
)
def review_surface(
    request: Request,
    instrument_position: int,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    reviewer, review_session = reviewer_session
    instrument_count = len(_instruments_for_session(db, review_session.id))
    if instrument_position < 1 or instrument_position > instrument_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        current_position=instrument_position,
    )
    context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
    context["reviewer_review_count"] = reviewer_review_count_for_user(db, user)
    context["current_position"] = instrument_position
    return _templates.TemplateResponse(
        request, "reviewer/review_surface.html", context
    )


@router.post(
    "/sessions/{session_id}/{instrument_position}/save",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_save(
    request: Request,
    instrument_position: int,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Save the form's response inputs for the URL position.

    PR γ wires the per-position filter alongside rendering-narrows-
    to-one-page (the GET surface renders only the URL position's
    instrument group, so the form body normally contains only its
    inputs; the filter is defense-in-depth against malformed POSTs
    that include cross-page assignment_ids).

    Server-side value validation rejects per-upsert (Integer / Decimal
    range and step). Invalid upserts are *not* persisted; the surface
    re-renders inline with the typed value still in the box plus the
    Invalid-values warning card. Valid upserts in the same batch save
    through.
    """
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    upserts = responses_service.parse_form_payload(
        {k: v for k, v in form.items() if isinstance(v, str)}
    )
    # Filter upserts to assignments whose instrument matches the URL
    # position. Inputs from other pages (a malformed POST or stale
    # form from before the rendering-narrows step) are silently
    # dropped — Save's scope is "this page only".
    sorted_instruments = sorted(
        _instruments_for_session(db, review_session.id).values(),
        key=lambda i: (i.order, i.id),
    )
    if not 1 <= instrument_position <= len(sorted_instruments):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    target_instrument_id = sorted_instruments[instrument_position - 1].id
    target_assignment_ids = {
        a.id
        for a in _load_assignments_with_relations(
            db, session_id=review_session.id, reviewer_id=reviewer.id
        )
        if a.instrument_id == target_instrument_id
    }
    upserts = [u for u in upserts if u.assignment_id in target_assignment_ids]
    result = responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    if result.errors:
        bad_values = {
            (e.assignment_id, e.field_key): e.value for e in result.errors
        }
        context = _surface_context(
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            current_position=instrument_position,
            errors=result.errors,
            bad_values=bad_values,
        )
        context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
        context["reviewer_review_count"] = reviewer_review_count_for_user(
            db, user
        )
        context["current_position"] = instrument_position
        return _templates.TemplateResponse(
            request,
            "reviewer/review_surface.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}/{instrument_position}",
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
    current_position = _read_current_position(form)
    upserts = responses_service.parse_form_payload(string_form)
    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    if not result.submitted:
        bad_values = {
            (e.assignment_id, e.field_key): e.value for e in result.errors
        }
        context = _surface_context(
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            current_position=current_position,
            missing=result.missing,
            errors=result.errors,
            bad_values=bad_values,
            show_incomplete_marks=not result.errors,
        )
        context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
        context["reviewer_review_count"] = reviewer_review_count_for_user(
            db, user
        )
        context["current_position"] = current_position
        return _templates.TemplateResponse(
            request,
            "reviewer/review_surface.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=submit_redirect_url(review_session, current_position),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/clear",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_clear(
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
    if form.get("confirm") != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    current_position = _read_current_position(form)
    responses_service.clear_all(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}/{current_position}",
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
