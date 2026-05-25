"""Reviewer response surface — the multi-instrument-aware
review table at ``/reviewer/sessions/{id}/{instrument_position}``,
its per-page Save, and the session-wide Submit / Clear.

Carved out of the single-file ``routes_reviewer.py`` in Segment
17B PR 1.

Reviewer surface — multi-instrument-aware URL pattern (Segment
11D follow-on, PR α onward):

- GET  /sessions/{id}                         → 303 to /sessions/{id}/1
- GET  /sessions/{id}/{instrument_position}   → renders the surface
- POST /sessions/{id}/{instrument_position}/save
- POST /sessions/{id}/submit                  → session-wide
- POST /sessions/{id}/clear                   → session-wide

Submit and Clear stay session-wide; their redirect targets read a
``current_position`` hidden form field so the reviewer lands back
on the page they were on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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
from app.services import date_formatting
from app.services import instruments as instruments_service
from app.services import relationships as relationships_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_reviewer_in_session,
)
from app.web.routes_reviewer._shared import (
    _NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD,
    _templates,
    reviewer_review_count_for_user,
)

router = APIRouter(prefix="/reviewer")


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


SessionStatusState = Literal["draft", "saved", "submitted"]


def _session_status(page_statuses: list["PageStatus"]) -> SessionStatusState | None:
    """Roll the per-page states into one session-wide status.

    ``submitted`` — every page submitted; ``draft`` — nothing started
    on any page; ``saved`` — anything in between (some saved but not
    all submitted). ``None`` when the reviewer has no pages, so the
    template renders no session pill.
    """
    if not page_statuses:
        return None
    states = {ps.state for ps in page_statuses}
    if states == {"submitted"}:
        return "submitted"
    if states == {"not_started"}:
        return "draft"
    return "saved"


@dataclass(frozen=True)
class GroupCompletion:
    """Per-instrument response-cell completion tallies for the
    Page-card progress pills. An "item" is one response cell — a
    single field for one reviewee. ``required_*`` counts cells whose
    field is required; ``all_*`` counts every response cell.
    """

    required_done: int
    required_total: int
    all_done: int
    all_total: int


def _group_completion(group_rows: list[dict], fields: list) -> GroupCompletion:
    """Tally completed vs total response cells for one instrument.

    ``required_done`` is derived from each row's ``missing_count``
    (DB-accurate); ``all_done`` counts display-cell values, which
    matches what the reviewer sees on a live surface.
    """
    n_rows = len(group_rows)
    required_field_count = sum(1 for f in fields if f.required)
    required_total = required_field_count * n_rows
    required_done = required_total - sum(
        r.get("missing_count", 0) for r in group_rows
    )
    all_total = len(fields) * n_rows
    all_done = sum(
        1
        for r in group_rows
        for cell in r.get("cells", [])
        if (cell.get("value") or "").strip()
    )
    return GroupCompletion(
        required_done=required_done,
        required_total=required_total,
        all_done=all_done,
        all_total=all_total,
    )


def _instruments_for_session(db: Session, session_id: int) -> dict[int, Instrument]:
    rows = db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalars()
    return {i.id: i for i in rows}


# A group row's identity cell lists at most this many member names
# before collapsing the rest to a "+N more" suffix (Segment 13C).
GROUP_MEMBER_NAME_LIMIT = 10


def _collapse_group_rows(
    per_assignment_rows: list[dict],
    *,
    group_key_by_assignment: dict[int, tuple[str, ...]],
    name_visible: bool,
) -> list[dict]:
    """Collapse a group-scoped instrument's per-assignment rows into
    one row per boundary-defined group (Segment 13C reviewer surface).

    Rows are partitioned by their assignment's group key; each
    partition yields one row carrying its lowest-id member assignment
    as the representative — response inputs key off it and the write
    fan-out spreads the answer to the rest. The representative row
    gains a ``group_identity`` block (boundary tag values + member
    names) and a ``group_label`` for aria text; its per-reviewee
    ``display_cells`` / ``sort_values`` are cleared.
    """
    partitions: dict[tuple[str, ...], list[dict]] = {}
    for row in per_assignment_rows:
        group_key = group_key_by_assignment.get(row["assignment"].id, ())
        partitions.setdefault(group_key, []).append(row)
    collapsed: list[dict] = []
    for group_key in sorted(partitions):
        members = sorted(
            partitions[group_key], key=lambda r: r["assignment"].id
        )
        representative = dict(members[0])
        names = sorted(r["assignment"].reviewee.name for r in members)
        shown = names[:GROUP_MEMBER_NAME_LIMIT]
        tag_line = ", ".join(v for v in group_key if v)
        representative["display_cells"] = []
        representative["sort_values"] = {}
        representative["group_identity"] = {
            "tag_line": tag_line,
            "member_names": shown,
            "extra_count": len(names) - len(shown),
            "show_members": name_visible,
        }
        representative["group_label"] = (
            tag_line or ", ".join(shown) or "the group"
        )
        collapsed.append(representative)
    return collapsed


def _reviewer_row_sort_key(row: dict, display_field_id: int) -> object | None:
    """Resolve one reviewer-surface row's value for a given
    ``display_field_id`` so ``views.order_rows_by_sort_spec``
    (Segment 13B PR 1) can sort.

    Reads from ``row["sort_values"]`` — a ``{display_field_id:
    value}`` dict pre-built by the row builder so the resolver
    stays O(1) per (row, field). The dict covers **all** display
    fields on the instrument (including the reviewee identity
    columns that the reviewer template renders in a dedicated
    identity cell rather than as separate display columns).

    Empty strings collapse to None so the helper's null-last
    sentinel takes over — operators sort to surface rows with
    data; empty cells should never bubble to the top.
    """
    value = row.get("sort_values", {}).get(display_field_id)
    if value in (None, ""):
        return None
    return value


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
    cookies: dict[str, str] | None = None,
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

    # All display fields per instrument — including the reviewee
    # identity columns (Name + Email) that ``display_fields_by_instrument``
    # excludes because the template renders them in a dedicated
    # identity cell rather than as separate columns. Segment 13B
    # PR 1's sort needs the full set so an operator can sort by
    # the Reviewee column.
    all_display_fields_by_instrument: dict[
        int, list[InstrumentDisplayField]
    ] = {}
    if instrument_ids:
        stmt = (
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id.in_(instrument_ids))
            .order_by(InstrumentDisplayField.order, InstrumentDisplayField.id)
        )
        for field in db.execute(stmt).scalars():
            all_display_fields_by_instrument.setdefault(
                field.instrument_id, []
            ).append(field)

    response_rows: dict[tuple[int, int], Response] = {}
    if assignments:
        stmt = select(Response).where(
            Response.assignment_id.in_([a.id for a in assignments])
        )
        for r in db.execute(stmt).scalars():
            response_rows[(r.assignment_id, r.response_field_id)] = r

    instruments = _instruments_for_session(db, review_session.id)
    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
    )

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
                    "label": instruments_service.display_field_label(display_field, session=review_session),
                    "value": instruments_service.display_field_value(
                        display_field,
                        assignment,
                        pair_context_lookup=pair_context_lookup,
                    ),
                    "is_profile_link": (
                        display_field.source_type == "reviewee"
                        and display_field.source_field == "profile_link"
                    ),
                }
            )
        # Sort lookup: ``display_field_id -> resolved value`` over
        # all display fields on this instrument (including the
        # identity ones that ``display_cells`` excludes). Lets the
        # Segment 13B sort spec key off any display field the
        # operator configured, not just the ones rendered as
        # separate columns.
        sort_values = {
            df.id: instruments_service.display_field_value(
                df,
                assignment,
                pair_context_lookup=pair_context_lookup,
            )
            for df in all_display_fields_by_instrument.get(
                assignment.instrument_id, []
            )
        }
        rows_by_instrument.setdefault(assignment.instrument_id, []).append(
            {
                "assignment": assignment,
                "cells": cells,
                "is_complete": is_complete,
                "missing_count": missing_count,
                "submitted_at": latest_submitted,
                "display_cells": display_cells,
                "sort_values": sort_values,
                "accepting": accepting,
                "show_values": show_values,
            }
        )

    # Segment 13C — collapse each group-scoped instrument's
    # per-assignment rows into one row per boundary-defined group.
    group_keys = responses_service.group_keys(
        db, assignments=assignments, session_id=review_session.id
    )
    for instrument_id, instrument in instruments.items():
        if instrument.group_kind is None:
            continue
        group_rows = rows_by_instrument.get(instrument_id)
        if not group_rows:
            continue
        # The group identity lists member names only when the
        # operator left the RevieweeName Display Field Included.
        name_visible = any(
            df.source_type == "reviewee"
            and df.source_field == "name"
            and df.visible
            for df in all_display_fields_by_instrument.get(instrument_id, [])
        )
        rows_by_instrument[instrument_id] = _collapse_group_rows(
            group_rows,
            group_key_by_assignment=group_keys,
            name_visible=name_visible,
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
        is_group = instrument.group_kind is not None
        # Reorder rows per the operator-default sort spec
        # (Segment 13B PR 1). NULL / empty spec → no-op
        # (insertion order). Display fields no longer on the
        # instrument silently drop from the sort cascade — see
        # ``views.order_rows_by_sort_spec`` for the render-time
        # defense. A group-scoped instrument's rows are already
        # collapsed to one per group and ordered by composed
        # group key; the only operator-controllable knob on a
        # group instrument is the Group sort sentinel
        # ``display_field_id == GROUP_IDENTITY_SORT_KEY`` (-1)
        # which lets the operator flip the order (asc keeps the
        # default; desc reverses).
        if is_group:
            from app.services.instruments import GROUP_IDENTITY_SORT_KEY

            for entry in (instrument.sort_display_fields or []):
                if entry.get("display_field_id") == GROUP_IDENTITY_SORT_KEY:
                    if entry.get("dir") == "desc":
                        group_rows = list(reversed(group_rows))
                    break
        if not is_group:
            # The full set — including identity-column display
            # fields the visible-cells filter excludes — so the
            # operator can sort by Reviewee name.
            known_display_field_ids = {
                df.id
                for df in all_display_fields_by_instrument.get(
                    instrument_id, []
                )
            }
            # Effective sort spec for this instrument (Segment 13B
            # Part 2 PR 5):
            #   1. Reviewer's per-browser cookie, if present + valid.
            #   2. Operator-default ``instrument.sort_display_fields``.
            # Both shapes are ``[{"display_field_id": int, "dir":
            # "asc|desc"}, ...]`` once normalised. The cookie keys
            # arrive as opaque strings (e.g. ``"reviewee.name"``,
            # ``"display:7"``); the helper decodes them against the
            # instrument's display-field set + the locked Reviewee
            # identity row.
            cookie_spec = views.decode_cookie_sort_spec_for_reviewer_surface(
                cookies=cookies or {},
                session_id=review_session.id,
                instrument_id=instrument_id,
                display_fields=all_display_fields_by_instrument.get(
                    instrument_id, []
                ),
            )
            effective_spec = (
                cookie_spec
                if cookie_spec is not None
                else instrument.sort_display_fields
            )
            group_rows = views.order_rows_by_sort_spec(
                group_rows,
                effective_spec,
                key_resolver=_reviewer_row_sort_key,
                known_display_field_ids=known_display_field_ids,
            )
        fields = fields_by_instrument.get(instrument_id, [])
        help_block_items = [
            f for f in fields if f.help_text and f.help_text_visible
        ]
        heading = views.instrument_heading(
            instrument=instrument,
            position=position_by_id[instrument_id],
            total_count=total_instrument_count,
        )
        # A group-scoped instrument renders no per-reviewee display
        # columns — the boundary tags compose the group-identity cell
        # instead — so its display-field header list is empty.
        # Per-column pixel widths the operator set by drag-resizing
        # Band 2 on the new-model card. ``widths_by_col_key`` keys
        # match the keys persisted on ``instrument.column_widths``:
        # ``"identity"`` for the always-rendered Reviewee / Group
        # identity column; ``"df_<id>"`` for each display field.
        widths_by_col_key: dict[str, int] = dict(instrument.column_widths or {})
        identity_width_px = widths_by_col_key.get("identity")
        display_field_headers = (
            []
            if is_group
            else [
                {
                    "field": df,
                    "label": instruments_service.display_field_label(
                        df, session=review_session
                    ),
                    "is_profile_link": (
                        df.source_type == "reviewee"
                        and df.source_field == "profile_link"
                    ),
                    "width_px": widths_by_col_key.get(f"df_{df.id}"),
                }
                for df in display_fields_by_instrument.get(instrument_id, [])
            ]
        )
        constraints = []
        for f in fields:
            summary = views.constraint_summary_for_field(f)
            if summary:
                constraints.append({"label": f.label, "summary": summary})
        instrument_groups.append(
            {
                "instrument": instrument,
                "is_group": is_group,
                "heading": heading,
                "position": position_by_id[instrument_id],
                "is_current": position_by_id[instrument_id] == current_position,
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "identity_width_px": identity_width_px,
                "has_custom_widths": bool(widths_by_col_key),
                "constraints": constraints,
                "show_status_col": show_incomplete_marks
                or any(r.get("submitted_at") for r in group_rows),
                "completion": _group_completion(group_rows, fields),
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
        "session_status": _session_status(page_statuses),
        "page_buttons": page_buttons,
        "current_position": current_position,
        "deadline_timezone_label": date_formatting.gmt_offset_zone_label(
            sessions_service.resolve_session_timezone(review_session),
            at=review_session.deadline,
        ),
    }


def submit_redirect_url(
    review_session: ReviewSession,
    position: int,
    *,
    fully_submitted: bool = False,
) -> str:
    """Where to send the reviewer after a successful submit.

    Returns the summary page URL (17B Phase 2 PR B) when the
    submit closed out the whole session — i.e. every assigned
    row now has ``submitted_at`` set — and the surface page
    otherwise so a per-instrument submit doesn't yank the
    reviewer off the page they pressed Submit from.
    """
    if fully_submitted:
        return f"/reviewer/sessions/{review_session.id}/summary"
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
    # Pre-open surface (18F Part 2). A reviewer with a roster row
    # (typically via an invitation sent ahead of activation) may
    # land here before the session is activated for responses;
    # render a dedicated "review opens later" page instead of
    # 403-ing or dropping them into the response form. The closed
    # case is handled later — the existing surface template
    # honours the per-instrument
    # ``responses_visible_when_closed`` toggle so reviewers can
    # still see their saved responses post-close, with the
    # "review now closed" banner overlaid via context.
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    db.refresh(review_session)
    if not lifecycle.is_ready(review_session):
        session_zone = sessions_service.resolve_session_timezone(
            review_session
        )
        deadline_text = (
            date_formatting.format_datetime(
                review_session.deadline, session_zone
            )
            if review_session.deadline
            else None
        )
        deadline_timezone_label = (
            date_formatting.gmt_offset_zone_label(
                session_zone, at=review_session.deadline
            )
            if review_session.deadline
            else None
        )
        return _templates.TemplateResponse(
            request,
            "reviewer/pre_open.html",
            {
                "user": user,
                "session": review_session,
                "deadline_text": deadline_text,
                "deadline_timezone_label": deadline_timezone_label,
            },
        )
    instrument_count = len(_instruments_for_session(db, review_session.id))
    if instrument_position < 1 or instrument_position > instrument_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        current_position=instrument_position,
        cookies=dict(request.cookies),
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
            cookies=dict(request.cookies),
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
            cookies=dict(request.cookies),
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
    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    return RedirectResponse(
        url=submit_redirect_url(
            review_session,
            current_position,
            fully_submitted=(
                state.total_assignments > 0
                and state.pill_state == "submitted"
            ),
        ),
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
