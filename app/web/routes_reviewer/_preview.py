"""Operator-side preview of the reviewer surface (Segment 10B-3).

``build_preview_context`` is the operator-facing mirror of
``_surface.py``'s ``_surface_context`` — it builds the same
reviewer-surface view shape with up to three rows (real
assignments padded with synthetic placeholders). It is consumed
by ``app/web/views/_previews.py`` for the Previews page; this
module exposes no routes of its own.

Carved out of the single-file ``routes_reviewer.py`` in Segment
17B PR 1.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import date_formatting
from app.services import instruments as instruments_service
from app.services import relationships as relationships_service
from app.services import sessions as sessions_service
from app.web import views
from app.web.routes_reviewer._shared import _NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD

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
    review_session: ReviewSession | None = None,
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
            "label": instruments_service.display_field_label(df, session=review_session),
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
    target_reviewer: Reviewer | None = None,
) -> dict:
    """Operator-side mirror of ``_surface.py``'s ``_surface_context``.

    Builds the reviewer-surface view shape with up to three rows: real
    assignments first (by ``Assignment.id`` ascending), padded with
    synthetic placeholders to reach three. When ``target_reviewer`` is
    provided (Segment 11F PR C — picker-driven previews hub), the real
    assignments are filtered to that reviewer so the iframe surfaces
    *that reviewer's* reviewees. With no target_reviewer (the legacy
    ``/preview`` redirect target / direct caller path) the query
    returns the first three assignments in the session regardless of
    reviewer. Per Segment 10B-3 D9 this is read-only — it does **not**
    call ``lifecycle.observe_deadline`` (which mutates the DB on a
    deadline crossing) and forces ``accepting=False`` on every row so
    the existing template's ``disabled_attr`` branch renders every
    input disabled.
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
            "current_page_n": 1,
            "page_count": 1,
            "prev_page_url": None,
            "next_page_url": None,
            "deadline_timezone_label": date_formatting.gmt_offset_zone_label(
                sessions_service.resolve_session_timezone(review_session),
                at=review_session.deadline,
            ),
            "preview_mode": True,
        }

    instrument_ids = [i.id for i in instruments]
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    stmt = (
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id.in_(instrument_ids))
        .where(InstrumentResponseField.visible.is_(True))
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

    assignments_stmt = (
        select(Assignment)
        .options(
            joinedload(Assignment.reviewee),
            joinedload(Assignment.instrument),
        )
        .where(
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
        )
    )
    if target_reviewer is not None:
        assignments_stmt = assignments_stmt.where(
            Assignment.reviewer_id == target_reviewer.id
        )
    real_assignments = list(
        db.execute(
            assignments_stmt.order_by(Assignment.id).limit(3)
        ).scalars()
    )
    pair_context_lookup = relationships_service.pair_context_lookup(
        db, review_session.id
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
                "label": instruments_service.display_field_label(df, session=review_session),
                "value": instruments_service.display_field_value(
                    df,
                    assignment,
                    pair_context_lookup=pair_context_lookup,
                ),
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
                    review_session=review_session,
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
                "label": instruments_service.display_field_label(df, session=review_session),
                "is_profile_link": (
                    df.source_type == "reviewee"
                    and df.source_field == "profile_link"
                ),
            }
            for df in display_fields
        ]
        constraints = []
        for f in fields:
            summary = views.constraint_summary_for_field(f)
            if summary:
                constraints.append({"label": f.label, "summary": summary})
        instrument_groups.append(
            {
                "instrument": instrument,
                # Operator preview renders group-scoped instruments
                # per-reviewee (un-collapsed); the surface-side group
                # block is a Segment 13C follow-up for this builder.
                "is_group": False,
                "heading": heading,
                "position": position,
                "rows": group_rows,
                "help_block_items": help_block_items,
                "display_fields": display_field_headers,
                "constraints": constraints,
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
        "missing": [],
        "errors": [],
        "show_incomplete_marks": False,
        "any_required": False,
        "any_accepting": False,
        "any_closed_with_hidden_values": False,
        "page_statuses": [],
        # Preview is single-render synthetic; the surface template's
        # action row is suppressed entirely in ``preview_mode``, so
        # nav-related context (page count, prev/next URLs) is moot
        # but kept here to match the live surface's context shape.
        "current_page_n": 1,
        "page_count": 1,
        "prev_page_url": None,
        "next_page_url": None,
        "deadline_timezone_label": date_formatting.gmt_offset_zone_label(
            sessions_service.resolve_session_timezone(review_session),
            at=review_session.deadline,
        ),
        "preview_mode": True,
    }
