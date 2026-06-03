"""Reviewer-surface template-context builder.

The ~490-LOC ``_surface_context`` function — single biggest function
in the package — plus the small loaders + the per-instrument
session-accepting guard it composes with. ``preview_mode`` (operator-
side full preview) is honoured here so the operator path renders
against identical plumbing without mutating session state.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, status
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
from app.services import date_formatting
from app.services import instruments as instruments_service
from app.services import relationships as relationships_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.web import views
from app.web.deps import request_correlation_id
from app.web.routes_reviewer._shared import (
    _NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD,
)

from ._group_collapse import _collapse_group_rows
from ._status import (
    PageStatus,
    _group_completion,
    _page_status_for_group,
    _session_status,
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

    # Segment 18K PR 5 — informational banner naming response
    # fields the reviewer has previously saved an answer on but
    # whose Band 2 chip the operator has since un-pinned. The
    # values stay in the DB for the audit / bundle export (Part 5
    # contract), but they no longer surface on form / summary /
    # CSV — the banner makes that disappearance visible so the
    # reviewer isn't silently missing answers. Read-only; no
    # action required.
    dropped_fields: list[tuple[str, str]] = []
    if response_rows:
        saved_field_ids = {r.response_field_id for r in response_rows.values()}
        hidden_rows = db.execute(
            select(InstrumentResponseField, Instrument)
            .join(
                Instrument,
                InstrumentResponseField.instrument_id == Instrument.id,
            )
            .where(InstrumentResponseField.id.in_(saved_field_ids))
            .where(InstrumentResponseField.visible.is_(False))
        ).all()
        for field, instrument in hidden_rows:
            inst_label = (
                instrument.short_label
                or instrument.name
                or f"Instrument {instrument.id}"
            )
            dropped_fields.append((inst_label, field.label))
        # De-dupe (multiple Response rows on the same hidden field
        # show up once) and stabilise order.
        dropped_fields = sorted(set(dropped_fields))

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

    # "Who can see what you wrote" transparency table — one
    # half-width card per instrument, sitting in the empty column
    # 2 of the intro grid. Read-only mirror of the operator's Band
    # 3 policy in plain language so the reviewer knows what
    # downstream audiences (the reviewee, observers) will see and
    # in what form.
    visibility_rows_by_instrument = views.build_reviewer_visibility_rows(
        db, [g["instrument"] for g in instrument_groups]
    )
    for group in instrument_groups:
        group["visibility_rows"] = visibility_rows_by_instrument.get(
            group["instrument"].id, []
        )

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
            f"/me/sessions/{review_session.id}/{safe_page_n - 1}"
            if safe_page_n > 1 else None
        )
        next_page_url = (
            f"/me/sessions/{review_session.id}/{safe_page_n + 1}"
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
        "dropped_fields": dropped_fields,
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
