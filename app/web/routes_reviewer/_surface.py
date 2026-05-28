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

Submit and Clear stay session-wide; their redirect targets are the
bare session URL ``/reviewer/sessions/{id}`` which 303s on to
``/1`` — post-Segment-18L the URL slot is the operator-defined
page number, so a "go back to where you were" round-trip is no
longer possible after a session-wide POST.
"""

from __future__ import annotations

from collections.abc import Callable
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
    label: str  # "#N {short_label}" when set, else bare "#N"
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


def _pages_for_session(db: Session, session_id: int) -> list[list[Instrument]]:
    """Walk the session's instruments in ``Instrument.order, Instrument.id``
    order and group them into operator-defined pages via the
    ``starts_new_page`` flag (Segment 18M). Each returned sublist is
    one page's instruments in order. The position-1 instrument's
    flag is ignored at render time (locked spec) so even if it
    carries ``starts_new_page=true`` from a stray operator action,
    it still anchors page 1.
    """
    ordered = sorted(
        _instruments_for_session(db, session_id).values(),
        key=lambda i: (i.order, i.id),
    )
    pages: list[list[Instrument]] = []
    current: list[Instrument] = []
    for idx, inst in enumerate(ordered):
        if idx > 0 and inst.starts_new_page:
            pages.append(current)
            current = []
        current.append(inst)
    if current:
        pages.append(current)
    return pages


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
        # Compose the group's tag line from every visible
        # ``reviewee.tag_*`` display field — matching the operator's
        # Band 2 preview, which joins each selected tag-pill value
        # with commas above the member names. Reading only the
        # boundary tags (via ``group_key``) silently drops any
        # non-boundary tag display field the operator chose. Falls
        # back to the boundary-key composition when there are zero
        # visible reviewee.tag_* display fields, so the line is
        # never blank when a boundary tag value exists.
        tag_values: list[str] = []
        for cell in members[0].get("display_cells", []) or []:
            field = cell.get("field")
            if field is None:
                continue
            source_type = getattr(field, "source_type", "")
            source_field = getattr(field, "source_field", "") or ""
            if source_type != "reviewee" or not source_field.startswith("tag_"):
                continue
            value = (cell.get("value") or "").strip()
            if value:
                tag_values.append(value)
        if tag_values:
            tag_line = ", ".join(tag_values)
        else:
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
    page_n: int = 1,
    missing: list[responses_service.MissingPosition] | None = None,
    errors: list[responses_service.ValidationError] | None = None,
    bad_values: dict[tuple[int, str], str] | None = None,
    show_incomplete_marks: bool = False,
    cookies: dict[str, str] | None = None,
    preview_mode: bool = False,
    page_url_builder: Callable[[int], str] | None = None,
) -> dict:
    # ``preview_mode`` (operator-side full preview, Segment 18Q):
    # render the reviewer surface against the same plumbing the
    # reviewer hits, but bypass the deadline-observer (which
    # mutates the DB on a crossing) and force ``accepting=True``
    # on every row so the form renders interactive regardless of
    # session lifecycle. Page nav URLs are rewritten via
    # ``page_url_builder`` so Prev/Next point back at the
    # operator-side preview route. The template's ``preview_mode``
    # branch swaps ``<form>`` for ``<div>`` and renders
    # Save/Discard/Submit as inert disabled buttons, so the
    # ``accepting=True`` override cannot leak writes.
    if not preview_mode:
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
            .where(InstrumentResponseField.visible.is_(True))
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
            and (
                preview_mode
                or lifecycle.session_accepts_responses(
                    review_session, instrument
                )
            )
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
        # Wave 3 PR iii — response-column widths migrated from
        # band2_state.response_fields[i].width_px into column_widths
        # under "rf_<id>" keys, mirroring the "df_<id>" pattern.
        response_field_width_by_id: dict[int, int] = {
            f.id: widths_by_col_key[f"rf_{f.id}"]
            for f in fields
            if f"rf_{f.id}" in widths_by_col_key
        }
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
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "identity_width_px": identity_width_px,
                "response_field_width_by_id": response_field_width_by_id,
                "has_custom_widths": bool(widths_by_col_key),
                "constraints": constraints,
                "show_status_col": show_incomplete_marks
                or any(r.get("submitted_at") for r in group_rows),
                "completion": _group_completion(group_rows, fields),
            }
        )
        flat_rows.extend(group_rows)

    # Per-instrument status pills in the overview card at the top of
    # the surface. Labels follow the same ``#N {short_label}`` (or
    # bare ``#N``) convention as the instrument heading so the pill
    # row reads as a quick index into the form below. Also feeds
    # ``_session_status`` for the lead rollup pill (Submitted /
    # Saved-not-submitted / Draft).
    page_statuses: list[PageStatus] = []
    instrument_groups_by_id = {
        g["instrument"].id: g for g in instrument_groups
    }
    for inst in sorted(instruments.values(), key=lambda i: (i.order, i.id)):
        if inst.id not in instrument_groups_by_id:
            continue
        position = position_by_id[inst.id]
        short = (inst.short_label or "").strip()
        label = f"#{position} {short}" if short else f"#{position}"
        page_statuses.append(
            PageStatus(
                position=position,
                label=label,
                state=_page_status_for_group(
                    instrument_groups_by_id[inst.id]["rows"]
                ),
            )
        )

    # Segment 18L multi-page (post-replan): filter ``instrument_groups``
    # to only the instruments on the operator-defined page being
    # rendered. Pages are derived from the per-session
    # ``starts_new_page`` flag via ``_pages_for_session``. ``page_n``
    # is the 1-based page index from the URL; out-of-range values
    # clamp to a single-page render (an empty page would be
    # confusing but never 404 here — the route 404s if the page is
    # truly missing).
    pages = _pages_for_session(db, review_session.id)
    page_count = len(pages) or 1
    safe_page_n = page_n if 1 <= page_n <= page_count else 1
    current_page_instrument_ids = {
        inst.id for inst in pages[safe_page_n - 1]
    } if pages else set()
    instrument_groups = [
        g for g in instrument_groups
        if g["instrument"].id in current_page_instrument_ids
    ]
    instrument_groups.sort(key=lambda g: g["position"])

    if preview_mode and page_url_builder is not None:
        prev_page_url = (
            page_url_builder(safe_page_n - 1) if safe_page_n > 1 else None
        )
        next_page_url = (
            page_url_builder(safe_page_n + 1)
            if safe_page_n < page_count
            else None
        )
    else:
        prev_page_url = (
            f"/reviewer/sessions/{review_session.id}/{safe_page_n - 1}"
            if safe_page_n > 1 else None
        )
        next_page_url = (
            f"/reviewer/sessions/{review_session.id}/{safe_page_n + 1}"
            if safe_page_n < page_count else None
        )

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
        "current_page_n": safe_page_n,
        "page_count": page_count,
        "prev_page_url": prev_page_url,
        "next_page_url": next_page_url,
        "deadline_timezone_label": date_formatting.gmt_offset_zone_label(
            sessions_service.resolve_session_timezone(review_session),
            at=review_session.deadline,
        ),
        "preview_mode": preview_mode,
    }


def submit_redirect_url(
    review_session: ReviewSession,
    *,
    fully_submitted: bool = False,
) -> str:
    """Where to send the reviewer after a successful submit.

    Returns the summary page URL (17B Phase 2 PR B) when the
    submit closed out the whole session — i.e. every assigned
    row now has ``submitted_at`` set — and the bare session URL
    otherwise (which 303s on to ``/1``). Post-Segment-18L the URL
    slot is the operator-defined page number, not the reviewer's
    last instrument position, so submit no longer attempts to
    return the reviewer to "the page they were on".
    """
    if fully_submitted:
        return f"/reviewer/sessions/{review_session.id}/summary"
    return f"/reviewer/sessions/{review_session.id}"


@router.get("/sessions/{session_id}", response_class=HTMLResponse, response_model=None)
def review_surface_default_position(session_id: int) -> RedirectResponse:
    """Bare-URL fallback. 303s to ``/{id}/1`` (page 1) per the
    Segment 18L multi-page replan. Auth happens on the destination
    handler; the redirect is harmless without it.
    """
    return RedirectResponse(
        url=f"/reviewer/sessions/{session_id}/1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/sessions/{session_id}/{page_n}",
    response_class=HTMLResponse,
    response_model=None,
)
def review_surface(
    request: Request,
    page_n: int,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Multi-page reviewer surface (Segment 18L replan). Renders
    one operator-defined page at a time. Pages are derived from
    ``Instrument.starts_new_page`` via
    ``_pages_for_session``; ``page_n`` is the 1-based page index
    from the URL.

    A "page" can contain one or many instruments — the operator
    chose the boundaries on the Setup → Instruments page in
    Segment 18M. Within a page, instruments stack without a
    horizontal separator; between pages, the reviewer navigates
    via the Prev / Next links in the page-nav row.
    """
    reviewer, review_session = reviewer_session
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    db.refresh(review_session)
    if not (
        lifecycle.is_ready(review_session)
        or lifecycle.is_expired(review_session)
    ):
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
    pages = _pages_for_session(db, review_session.id)
    page_count = len(pages) or 1
    if page_n < 1 or page_n > page_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        page_n=page_n,
        cookies=dict(request.cookies),
    )
    context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
    context["reviewer_review_count"] = reviewer_review_count_for_user(db, user)
    return _templates.TemplateResponse(
        request, "reviewer/review_surface.html", context
    )


@router.post(
    "/sessions/{session_id}/{page_n}/save",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_save(
    request: Request,
    page_n: int,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Save the form's response inputs for the given operator-defined
    page (Segment 18L multi-page replan).

    The form on each page carries only that page's assignment inputs
    (the GET handler filters ``instrument_groups`` to the current
    page). A defense-in-depth filter still drops cross-page
    assignment ids so a stale form posting from a previous render
    can't accidentally write to other pages.

    Server-side value validation rejects per-upsert (Integer /
    Decimal range and step). Invalid upserts are not persisted; the
    surface re-renders inline with the typed value still in the box
    plus the Invalid-values warning card. Valid upserts in the same
    batch save through.
    """
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    upserts = responses_service.parse_form_payload(
        {k: v for k, v in form.items() if isinstance(v, str)}
    )
    pages = _pages_for_session(db, review_session.id)
    if page_n < 1 or page_n > len(pages):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    target_instrument_ids = {inst.id for inst in pages[page_n - 1]}
    target_assignment_ids = {
        a.id
        for a in _load_assignments_with_relations(
            db, session_id=review_session.id, reviewer_id=reviewer.id
        )
        if a.instrument_id in target_instrument_ids
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
            page_n=page_n,
            errors=result.errors,
            bad_values=bad_values,
            cookies=dict(request.cookies),
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
        url=f"/reviewer/sessions/{review_session.id}/{page_n}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 18L PR 1a — consolidated save endpoint.
#
# Walks every upsert in the form payload (no per-position filter) and
# persists in one ``responses_service.save_draft`` call. The new
# canonical save target for the upcoming single-page render in PR 1b.
# Audit emit registers ``assignments_touched`` + ``responses_saved``
# in ``detail.counts`` (PR 1a swapped the keys cleanly; the legacy
# ``saved`` + ``validation_errors`` retire in the same change).
#
# Lands inert: the template's <form action> still points at the
# legacy positional save endpoint. PR 1b flips the form action,
# drops the legacy POST + the per-position filter, and wires the
# inline error re-render. Until then this endpoint is only reachable
# directly (tests, scripted callers).
# --------------------------------------------------------------------------- #


@router.post(
    "/sessions/{session_id}/save",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_save_consolidated(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save every upsert in the form payload in one round-trip.

    No per-position filter — the form normally carries inputs for
    every instrument the reviewer has assignments on (PR 1b's
    single-page render is the natural source). Server-side value
    validation rejects per-upsert as before; invalid upserts are not
    persisted, valid ones in the same batch save through. Errors
    surface as HTTP 400 with a JSON detail in PR 1a; PR 1b wires the
    inline single-page re-render that highlights the offending cells
    on top of the saved values.

    Always redirects on success to the bare session URL — which
    today 303s on to ``/{id}/1`` (positional render) and after PR 1b
    will be the single-page render directly. Either way the
    operator-visible behaviour from this endpoint is "go back to the
    surface".
    """
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    upserts = responses_service.parse_form_payload(
        {k: v for k, v in form.items() if isinstance(v, str)}
    )
    result = responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    if result.errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "errors": [
                    {
                        "assignment_id": e.assignment_id,
                        "field_key": e.field_key,
                        "value": e.value,
                    }
                    for e in result.errors
                ],
            },
        )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}",
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
            fully_submitted=(
                state.total_assignments > 0
                and state.pill_state == "submitted"
            ),
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/recall",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewer_recall(
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Roll the reviewer's submission back to draft and land them
    on the form to edit it. The summary page's "Recall my
    submission" button posts here.

    Gated on session status ``ready`` only — a session that's
    been closed (``expired``) or archived has no live form to
    return to, so recall is meaningless. Per-instrument
    ``accepting_responses`` flips by the operator don't block
    recall; the reviewer is putting their values back into the
    draft pool to keep editing them on whichever instruments
    are still open.
    """
    reviewer, review_session = reviewer_session
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    db.refresh(review_session)
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Recall is only allowed while the session is ready; "
                f"session status is {review_session.status!r}."
            ),
        )
    responses_service.recall(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/reviewer/sessions/{review_session.id}/1",
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
