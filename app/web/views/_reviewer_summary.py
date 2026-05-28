"""Reviewer per-session participation-summary view shape.

Segment 17B Phase 2 PR B. Translates the reviewer's responses on
one session into a list of per-instrument sections the
``reviewer/summary.html`` template renders. Read-only — no edit
affordances, no save / submit forms.

The summary page lives alongside the response surface; once a
reviewer has submitted every assigned row on a session the
submit-flow redirect lands them here instead of back on the
surface. The page also stays reachable later (from PR A's
dashboard, the Session column links here when Reviewer Status
is ``submitted``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import instruments as instruments_service
from app.services import relationships as relationships_service
from app.services import responses as responses_service


# Cap on the member-name list rendered in a group-scoped row's
# identity cell — mirrors ``routes_reviewer/_surface.GROUP_MEMBER_NAME_LIMIT``.
GROUP_MEMBER_NAME_LIMIT = 10


@dataclass(frozen=True)
class SummaryFieldCol:
    """One response-field column in a per-instrument summary table."""

    field_key: str
    label: str
    # ``True`` when the operator marked the field required — the
    # template appends ``*`` to the header to mirror the response
    # surface.
    required: bool = False
    # Operator-set pixel width from
    # ``Instrument.column_widths["rf_<id>"]``. ``None`` when the
    # operator hasn't drag-resized this column on the Band 2
    # editor; the template then lets it auto-distribute.
    width_px: int | None = None
    # Column-class hints mirroring the reviewer surface
    # (``review_surface.html`` lines 271-274 / 331-334).
    # ``is_narrow``: Integer / Decimal columns — render with
    # ``class="rs-narrow"`` (``width: 1%; white-space: nowrap``)
    # so a short header like "Rating *" doesn't wrap.
    # ``is_textlong``: String columns with ``max_length > 100``
    # — render with ``class="rs-textlong"`` (``min-width: 14em``)
    # so long-comment columns claim enough horizontal room.
    # Skipped for group-scoped instruments (matches the form;
    # group tables are ``table-layout: fixed`` with bespoke
    # widths). ``None``-typed fields default to neither.
    is_narrow: bool = False
    is_textlong: bool = False


@dataclass(frozen=True)
class SummaryDisplayCol:
    """One display-field column header (per-reviewee instruments only;
    group-scoped instruments don't render display columns)."""

    field_id: int
    label: str
    is_profile_link: bool
    width_px: int | None = None


@dataclass(frozen=True)
class SummaryDisplayCell:
    """One display-field value cell — mirrors the reviewer surface's
    ``row.display_cells[*]``."""

    value: str
    is_profile_link: bool


@dataclass(frozen=True)
class SummaryGroupIdentity:
    """The composed identity cell for a group-scoped instrument row.

    Mirrors the reviewer surface's ``row.group_identity``: boundary-
    tag values comma-joined (``tag_line``), capped member-name list
    (``member_names`` + ``extra_count``), and the operator's
    ``Include`` toggle on the ``RevieweeName`` display field
    (``show_members``)."""

    tag_line: str
    member_names: list[str]
    extra_count: int
    show_members: bool
    fallback_label: str


@dataclass(frozen=True)
class SummaryRow:
    """One row in a per-instrument summary table.

    Per-reviewee instruments: ``reviewee_name`` + ``reviewee_email``
    drive the identity cell (Name + email — same shape as the
    response surface), ``display_cells`` carries the per-display-
    field values, ``group_identity`` is ``None``.

    Group-scoped instruments: ``group_identity`` carries the
    composed identity block (tag line + member names),
    ``display_cells`` is empty, ``reviewee_name`` / ``reviewee_email``
    only carry the row's sort label (the group identity's
    ``fallback_label``).
    """

    reviewee_name: str
    reviewee_email: str | None
    display_cells: list[SummaryDisplayCell]
    values: list[str]
    group_identity: SummaryGroupIdentity | None = None


@dataclass(frozen=True)
class SummarySection:
    """One per-instrument section on the summary page.

    ``position`` is the 1-based positional index the surface route
    uses (``Instrument.order, Instrument.id`` ordered) so the
    section heading matches the reviewer's surface navigation.
    """

    # Heading shown on the section card. Mirrors the form's
    # heading composition (``views._instruments.instrument_heading``):
    # multi-instrument sessions get ``"#{N}: {short}"`` (or bare
    # ``"#{N}"`` when ``short_label`` is unset); single-instrument
    # sessions get just the short label, falling back to
    # ``instrument.name`` when no short label exists.
    heading_title: str
    position: int
    is_group: bool
    display_field_cols: list[SummaryDisplayCol]
    field_cols: list[SummaryFieldCol]
    rows: list[SummaryRow]
    # Identity column ("Reviewee" or "Group") width, from
    # ``Instrument.column_widths["identity"]``. ``None`` when the
    # operator hasn't drag-resized it.
    identity_width_px: int | None = None
    # ``True`` iff the operator drag-resized at least one column
    # on this instrument (identity, any display field, or any
    # response field). When ``True`` the template renders a
    # ``<colgroup>`` + sets ``table-layout: fixed`` on the
    # table so the explicit widths take effect.
    has_custom_widths: bool = False


@dataclass(frozen=True)
class ReviewerSummaryContext:
    """The full context the ``reviewer/summary.html`` template
    consumes."""

    session: ReviewSession
    sections: list[SummarySection]
    last_submitted_at: datetime | None


def build_reviewer_summary_context(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
) -> ReviewerSummaryContext:
    """Build the read-only summary context for one reviewer.

    Walks the session's instruments in positional order; for each
    one the reviewer has at least one ``Response`` on, emits a
    section with the field columns and one row per reviewee (or
    one row per group on a group-scoped instrument). Instruments
    the reviewer wasn't assigned to are omitted from the section
    list. ``last_submitted_at`` is the most recent ``submitted_at``
    across the reviewer's responses on the session — the page's
    "Submitted on ..." caption.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )

    # Fan-out / group identity index for group-scoped instruments.
    assignments = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id,
                Assignment.reviewer_id == reviewer.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    assignment_by_id = {a.id: a for a in assignments}
    group_key_by_assignment = responses_service.group_keys(
        db, assignments=assignments, session_id=review_session.id
    )

    # Visible display fields per instrument — excluding the
    # Name / Email identity slots that the surface template
    # renders in a dedicated identity cell rather than as
    # separate columns. Mirrors
    # ``routes_reviewer/_surface.py`` lines 370-380.
    from app.web.routes_reviewer._shared import (
        _NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD,
    )

    instrument_ids = {a.instrument_id for a in assignments}
    display_fields_by_instrument: dict[
        int, list[InstrumentDisplayField]
    ] = {}
    all_display_fields_by_instrument: dict[
        int, list[InstrumentDisplayField]
    ] = {}
    if instrument_ids:
        stmt = (
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id.in_(instrument_ids))
            .where(InstrumentDisplayField.visible.is_(True))
            .where(_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD)
            .order_by(
                InstrumentDisplayField.order, InstrumentDisplayField.id
            )
        )
        for field in db.execute(stmt).scalars():
            display_fields_by_instrument.setdefault(
                field.instrument_id, []
            ).append(field)
        all_stmt = (
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id.in_(instrument_ids))
            .order_by(
                InstrumentDisplayField.order, InstrumentDisplayField.id
            )
        )
        for field in db.execute(all_stmt).scalars():
            all_display_fields_by_instrument.setdefault(
                field.instrument_id, []
            ).append(field)

    pair_context = relationships_service.pair_context_lookup(
        db, review_session.id
    )

    def _identity_for_group(
        instrument_id: int, group_key: tuple[str, ...]
    ) -> SummaryGroupIdentity:
        """Compose a group-row's identity block — reviewee-tag
        values joined by ", " above the member-name list, capped
        at GROUP_MEMBER_NAME_LIMIT with a ``+N more`` suffix.

        ``tag_line`` mirrors the reviewer surface's
        ``_collapse_group_rows`` composition: walk every visible
        ``reviewee.tag_*`` display field on the instrument (NOT
        just the boundary tags) and pick the representative
        member's value for each, joined comma-separated in
        display-field order. Falls back to the boundary-key
        composition when no ``reviewee.tag_*`` display field is
        visible — keeps the cell from going blank when the
        operator picked a non-tag boundary or hid every tag.
        ``show_members`` honours the operator's Include toggle
        on the RevieweeName display field (same source as the
        surface)."""
        group_members = [
            assignment
            for assignment in assignments
            if assignment.instrument_id == instrument_id
            and group_key_by_assignment.get(assignment.id) == group_key
        ]
        member_names = sorted(a.reviewee.name for a in group_members)
        shown = member_names[:GROUP_MEMBER_NAME_LIMIT]
        extra = len(member_names) - len(shown)

        # Walk every visible reviewee.tag_* display field on the
        # instrument and pull the representative member's value
        # for each. The reviewer surface does the same so the
        # two tables agree on the identity composition.
        tag_values: list[str] = []
        representative = (
            min(group_members, key=lambda a: a.id) if group_members else None
        )
        if representative is not None:
            for df in display_fields_by_instrument.get(instrument_id, []):
                if (
                    df.source_type != "reviewee"
                    or not (df.source_field or "").startswith("tag_")
                ):
                    continue
                value = instruments_service.display_field_value(
                    df, representative, pair_context_lookup=pair_context
                )
                value = (value or "").strip()
                if value:
                    tag_values.append(value)
        if tag_values:
            tag_line = ", ".join(tag_values)
        else:
            tag_line = ", ".join(v for v in group_key if v)

        name_visible = any(
            df.source_type == "reviewee"
            and df.source_field == "name"
            and df.visible
            for df in all_display_fields_by_instrument.get(
                instrument_id, []
            )
        )
        return SummaryGroupIdentity(
            tag_line=tag_line,
            member_names=shown,
            extra_count=extra,
            show_members=name_visible,
            fallback_label=(
                tag_line or ", ".join(shown) or "the group"
            ),
        )

    # Pull all of the reviewer's responses + denormalised reviewee /
    # field / instrument context in one query.
    rows = list(
        db.execute(
            select(
                Response,
                Reviewee,
                Instrument,
                InstrumentResponseField,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
            .join(Instrument, Assignment.instrument_id == Instrument.id)
            .join(
                InstrumentResponseField,
                Response.response_field_id == InstrumentResponseField.id,
            )
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.reviewer_id == reviewer.id)
        ).all()
    )

    # Index responses by (instrument_id, row_key, field_id).
    # For group-scoped instruments, row_key is the boundary
    # ``group_key`` tuple; for per-reviewee instruments it's
    # the reviewee.id. A separate ``reviewee_index`` carries
    # the reviewee object per row for identity rendering
    # (per-reviewee rows) and for the group's member-list
    # composition (group rows pull names directly from
    # ``assignments``, not via this index).
    cells: dict[tuple[int, object, int], str] = {}
    row_order: dict[int, list[object]] = {}
    reviewee_by_row: dict[tuple[int, int], Reviewee] = {}
    representative_assignment: dict[tuple[int, object], Assignment] = {}
    for response, reviewee, instrument, field in rows:
        group_key = group_key_by_assignment.get(response.assignment_id)
        if group_key is not None:
            key: object = group_key
        else:
            key = reviewee.id
            reviewee_by_row[(instrument.id, reviewee.id)] = reviewee
        cell_key = (instrument.id, key, field.id)
        # Group-scoped fan-out: the same (reviewer, instrument,
        # group, field) cell appears once per member; the first
        # one wins (they all carry the same value by the
        # fan-out invariant).
        if cell_key in cells:
            continue
        cells[cell_key] = (
            response.value if response.value is not None else ""
        )
        order_list = row_order.setdefault(instrument.id, [])
        if key not in order_list:
            order_list.append(key)
        rep_key = (instrument.id, key)
        if rep_key not in representative_assignment:
            assignment = assignment_by_id.get(response.assignment_id)
            if assignment is not None:
                representative_assignment[rep_key] = assignment

    last_submitted_at: datetime | None = None
    for response, _, _, _ in rows:
        if response.submitted_at is None:
            continue
        if last_submitted_at is None or response.submitted_at > last_submitted_at:
            last_submitted_at = response.submitted_at

    sections: list[SummarySection] = []
    total_instrument_count = len(instruments)
    for position, instrument in enumerate(instruments, start=1):
        if instrument.id not in row_order:
            continue
        is_group = instrument.group_kind is not None
        # Mirror the response form's heading composition
        # (``views._instruments.instrument_heading``): the
        # multi-instrument case carries the ``#{N}`` prefix
        # so the reviewer reads the same heading on the summary
        # they read on the form. Single-instrument sessions drop
        # the prefix; bare ``instrument.name`` is the fallback
        # when no short label is set so the summary card always
        # has *some* heading to render.
        short_label = (instrument.short_label or "").strip()
        if total_instrument_count == 1:
            heading_title = short_label or instrument.name
        elif short_label:
            heading_title = f"#{position}: {short_label}"
        else:
            heading_title = f"#{position}"
        # Filter response fields by ``visible`` so the summary
        # table mirrors the reviewer surface form
        # (``routes_reviewer/_surface.py`` filters the same way).
        # A response field whose Band 2 chip is un-pinned is not
        # rendered to the reviewer on the form, and must not
        # surface as a summary column either.
        fields = sorted(
            (f for f in instrument.response_fields if f.visible),
            key=lambda f: (f.order, f.id),
        )
        instrument_display_fields = (
            []
            if is_group
            else display_fields_by_instrument.get(instrument.id, [])
        )
        # Operator-set per-column pixel widths from the Band 2
        # editor live on ``instrument.column_widths``. Keys:
        # ``"identity"`` for the Reviewee/Group column,
        # ``"df_<id>"`` for each display field (per-reviewee
        # instruments only — group-scoped tables render no
        # display columns), and ``"rf_<id>"`` for each response
        # field. Mirrors the reviewer-surface render path in
        # ``routes_reviewer/_surface.py``.
        widths_by_col_key: dict[str, int] = dict(
            instrument.column_widths or {}
        )
        identity_width_px = widths_by_col_key.get("identity")
        display_field_cols = [
            SummaryDisplayCol(
                field_id=df.id,
                label=instruments_service.display_field_label(
                    df, session=review_session
                ),
                is_profile_link=(
                    df.source_type == "reviewee"
                    and df.source_field == "profile_link"
                ),
                width_px=widths_by_col_key.get(f"df_{df.id}"),
            )
            for df in instrument_display_fields
        ]
        field_cols = [
            SummaryFieldCol(
                field_key=f.field_key,
                label=f.label,
                required=bool(f.required),
                width_px=widths_by_col_key.get(f"rf_{f.id}"),
                is_narrow=(
                    not is_group
                    and f.data_type in ("Integer", "Decimal")
                ),
                is_textlong=(
                    not is_group
                    and f.data_type == "String"
                    and ((f.validation or {}).get("max_length") or 0) > 100
                ),
            )
            for f in fields
        ]
        has_custom_widths = (
            identity_width_px is not None
            or any(col.width_px is not None for col in display_field_cols)
            or any(col.width_px is not None for col in field_cols)
        )

        # Stable display order — same sort as the surface (by
        # reviewee name or composed group label).
        def _row_sort_label(key: object) -> str:
            if isinstance(key, tuple):
                # Group row — sort by tag values + member names.
                identity = _identity_for_group(instrument.id, key)
                return (identity.fallback_label or "").lower()
            reviewee = reviewee_by_row.get((instrument.id, key))
            return (reviewee.name if reviewee else "").lower()

        ordered_keys = sorted(row_order[instrument.id], key=_row_sort_label)
        section_rows: list[SummaryRow] = []
        for key in ordered_keys:
            values = [
                cells.get((instrument.id, key, f.id), "") for f in fields
            ]
            if isinstance(key, tuple):
                # Group-scoped row.
                identity = _identity_for_group(instrument.id, key)
                section_rows.append(
                    SummaryRow(
                        reviewee_name=identity.fallback_label,
                        reviewee_email=None,
                        display_cells=[],
                        values=values,
                        group_identity=identity,
                    )
                )
                continue
            # Per-reviewee row — compose Name + email identity
            # and the per-display-field cells the surface would
            # have rendered.
            reviewee = reviewee_by_row.get((instrument.id, key))
            assignment = representative_assignment.get((instrument.id, key))
            display_cells = []
            if assignment is not None:
                for df in instrument_display_fields:
                    value = instruments_service.display_field_value(
                        df,
                        assignment,
                        pair_context_lookup=pair_context,
                    )
                    display_cells.append(
                        SummaryDisplayCell(
                            value=value,
                            is_profile_link=(
                                df.source_type == "reviewee"
                                and df.source_field == "profile_link"
                            ),
                        )
                    )
            section_rows.append(
                SummaryRow(
                    reviewee_name=reviewee.name if reviewee else "",
                    reviewee_email=(
                        reviewee.email_or_identifier if reviewee else None
                    ),
                    display_cells=display_cells,
                    values=values,
                )
            )
        sections.append(
            SummarySection(
                heading_title=heading_title,
                position=position,
                is_group=is_group,
                display_field_cols=display_field_cols,
                field_cols=field_cols,
                rows=section_rows,
                identity_width_px=identity_width_px,
                has_custom_widths=has_custom_widths,
            )
        )

    return ReviewerSummaryContext(
        session=review_session,
        sections=sections,
        last_submitted_at=last_submitted_at,
    )


__all__ = [
    "ReviewerSummaryContext",
    "SummaryDisplayCell",
    "SummaryDisplayCol",
    "SummaryFieldCol",
    "SummaryGroupIdentity",
    "SummaryRow",
    "SummarySection",
    "build_reviewer_summary_context",
]
