"""Reviewee per-session results view shape.

Translates the responses that have been keyed about one reviewee on
one session into a list of per-instrument sections the
``reviewer/results.html`` template renders. Read-only — no edit
affordances, no save / submit forms.

This is the reviewee's mirror of the reviewer summary page
(``app/web/views/_reviewer_summary.py``); the heavy lifting is
intentionally similar so the surfaces read consistently. The
differences are intentional:

- **Scope** — rows are filtered to assignments where the
  signed-in reviewee is the *reviewee* (``Assignment.reviewee_id
  == reviewee.id``), not the reviewer.
- **Identity column** — the first cell shows the *reviewer* who
  authored each response (name + email), not the reviewee
  themselves. The reviewee already knows it's about them; what
  they want to see is who said what.
- **Visibility policy gate** — instruments are filtered through
  the persisted ``reviewee`` policy. Three modes render: ``raw``
  (full identification + values), ``anonymized`` (same table,
  identification cells dashed, values still shown) and
  ``summarized`` (per-data-type aggregation — the operator-
  facing "Anonymized summaries" chip; identification columns
  collapse into a single counts cell, rows collapse into one,
  each response field renders an aggregate keyed by its
  ``data_type``). An instrument with no row, or with both
  windows off, contributes nothing.
- **Window gate** — even when the policy says Raw or Anonymized,
  the relevant session-level window must be currently open for
  values to surface. Pre-release (anchor not yet set / not yet
  reached) renders the table scaffolding with empty cells;
  explicitly-closed windows drop the section entirely. The
  resolver consumes ``session_lifecycle.is_ready``
  (while_ongoing) and
  ``session_lifecycle.is_response_release_window_open``
  (after_release). Archived sessions force every audience to
  off at the route layer.

Reviewee-identity display fields (Name / Email / Profile) are
dropped from the per-row display cells — they'd just repeat the
signed-in reviewee on every row. Tag columns and other
non-identity display fields stay (and get dashed in
``anonymized`` mode).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

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
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
from app.web.views._reviewer_summary import (
    GROUP_MEMBER_NAME_LIMIT,
    SummaryDisplayCell,
    SummaryDisplayCol,
    SummaryFieldCol,
    SummaryGroupIdentity,
)


@dataclass(frozen=True)
class ResultsRow:
    """One row in a per-instrument results table.

    Per-reviewee instruments: ``reviewer_name`` + ``reviewer_email``
    drive the identity cell — Name + email of the reviewer who
    keyed the response. ``display_cells`` carries the
    non-identity display-field values (tag columns, etc).

    Group-scoped instruments: a single row per reviewer who
    responded about the group; ``group_identity`` is omitted
    because the results page is anchored on the signed-in
    reviewee (they know which group they're in), so the
    reviewer column carries the meaningful identity.
    """

    reviewer_name: str
    reviewer_email: str | None
    display_cells: list[SummaryDisplayCell]
    values: list[str]


@dataclass(frozen=True)
class SummarizedFieldCell:
    """Per-field aggregate cell in a ``summarized`` section.

    ``data_type`` drives the template render branch:

    - ``"Integer"`` / ``"Decimal"`` — numeric central-tendency
      + range. ``average`` / ``median`` are the rounded mean and
      median over non-empty submitted values; ``min_value`` /
      ``max_value`` are the extremes. ``response_count`` is how
      many values fed every aggregate; zero means the section
      has nothing to summarize.
    - ``"List"`` — raw frequency of each list option plus its
      share of the total. Every option declared on the field
      surfaces (so a zero stays visible) in field-declaration
      order; each tuple is ``(choice, count, percentage)``.
    - ``"String"`` — total characters across submissions plus
      the per-response average, on the rationale that the
      length distribution is the most defensible summary we
      can give without semantic analysis. ``response_count``
      is the number of non-empty string responses.
    """

    data_type: str
    response_count: int = 0
    # Numerical
    average: float | None = None
    median: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    # List — ``(choice, count, percentage)``; percentage is a
    # float in ``[0, 100]`` rounded to 1 decimal place.
    frequencies: tuple[tuple[str, int, float], ...] = ()
    # String
    total_length: int = 0
    average_length: float | None = None


@dataclass(frozen=True)
class SummarizedRow:
    """The single aggregate row that replaces per-reviewer rows
    in ``summarized`` mode. The identification cell carries the
    two counts (reviewers assigned + reviewers with any non-empty
    submitted value); ``field_cells`` are aligned 1:1 with the
    section's ``field_cols`` list."""

    reviewers_assigned: int
    reviewers_with_responses: int
    field_cells: list[SummarizedFieldCell]


@dataclass(frozen=True)
class ResultsSection:
    """One per-instrument section on the reviewee results page.

    Mirrors :class:`SummarySection` from the reviewer summary
    page; the header / column / width plumbing reads identically.
    Only the row shape differs (see :class:`ResultsRow`).
    """

    heading_title: str
    position: int
    is_group: bool
    display_field_cols: list[SummaryDisplayCol]
    field_cols: list[SummaryFieldCol]
    rows: list[ResultsRow]
    identity_width_px: int | None = None
    has_custom_widths: bool = False
    # The operator-facing mode the resolver picked for this
    # instrument. ``"raw"`` shows identification + values;
    # ``"anonymized"`` (the operator's "Anonymized responses"
    # chip) shows the same table but every identification cell
    # (Reviewer name + email + display-field values like tags)
    # renders as the muted em-dash placeholder. ``"summarized"``
    # (the operator's "Anonymized summaries" chip) collapses
    # identification into a single counts cell, rows into one,
    # and renders per-data-type aggregates in each response-field
    # column; ``rows`` is empty and ``summarized_row`` carries
    # the aggregate payload.
    mode: str = "raw"
    summarized_row: SummarizedRow | None = None


@dataclass(frozen=True)
class RevieweeResultsContext:
    """The full context the ``reviewer/results.html`` template
    consumes for a reviewee viewing the responses about them."""

    session: ReviewSession
    sections: list[ResultsSection]


def _summarize_field(
    field: InstrumentResponseField, raw_values: list[str]
) -> SummarizedFieldCell:
    """Per-data-type aggregation for one response field's
    submitted values. ``raw_values`` is the list of non-empty
    submitted strings keyed for this field across every assigned
    reviewer for this instrument-reviewee pair."""
    data_type = field.data_type
    if data_type in ("Integer", "Decimal"):
        parsed: list[float] = []
        for value in raw_values:
            try:
                parsed.append(float(value))
            except (TypeError, ValueError):
                continue
        if not parsed:
            return SummarizedFieldCell(data_type=data_type)
        mean = sum(parsed) / len(parsed)
        return SummarizedFieldCell(
            data_type=data_type,
            response_count=len(parsed),
            average=round(mean, 2),
            median=round(statistics.median(parsed), 2),
            min_value=round(min(parsed), 2),
            max_value=round(max(parsed), 2),
        )
    if data_type == "List":
        choices_csv = field._inline_list_csv or ""
        choices = [
            opt.strip() for opt in choices_csv.split(",") if opt.strip()
        ]
        counts: dict[str, int] = {choice: 0 for choice in choices}
        for value in raw_values:
            if value in counts:
                counts[value] += 1
            else:
                # Stored value that no longer matches a declared
                # choice (e.g. the operator edited the option set
                # after responses landed). Surface it so the
                # aggregate stays faithful to what's in the table.
                counts.setdefault(value, 0)
                counts[value] += 1
        total = sum(counts.values())
        frequencies = tuple(
            (
                choice,
                count,
                round(100 * count / total, 1) if total else 0.0,
            )
            for choice, count in counts.items()
        )
        return SummarizedFieldCell(
            data_type=data_type,
            response_count=total,
            frequencies=frequencies,
        )
    # String (and any unrecognised type): summarize by length.
    lengths = [len(v) for v in raw_values]
    if not lengths:
        return SummarizedFieldCell(data_type=data_type or "String")
    total_length = sum(lengths)
    return SummarizedFieldCell(
        data_type=data_type or "String",
        response_count=len(lengths),
        total_length=total_length,
        average_length=round(total_length / len(lengths), 1),
    )


def build_reviewee_results_context(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewee: Reviewee,
) -> RevieweeResultsContext:
    """Build the read-only results context for one reviewee.

    Walks the session's instruments in positional order. For each
    instrument, the section renders whenever the operator has
    authored Raw on the ``reviewee`` policy for at least one
    window (Session-ongoing or Responses-released); other modes
    don't render in this slice. **Submitted values** only fill
    in when the corresponding window is currently open —
    otherwise the cells stay empty so the reviewee can see who
    the would-be reviewers are without prematurely seeing their
    responses. Operators can therefore author Raw before
    setting the release-from anchor and still get the empty-
    rows preview surface; once the anchor passes, the values
    arrive automatically.
    """
    # Archive forces every audience off — short-circuit before
    # touching the policy table.
    if lifecycle.is_archived(review_session):
        return RevieweeResultsContext(
            session=review_session, sections=[]
        )

    while_ongoing_open = lifecycle.is_ready(review_session)
    after_release_open = lifecycle.is_response_release_window_open(
        review_session
    )
    # Distinguish "pre-release" (anchor not yet set / not yet
    # reached — operator is still configuring) from "explicitly
    # closed" (the operator stamped a close datetime or pressed
    # Stop release). Pre-release is fine — the scaffolding is a
    # preview the operator can use. Closed retires the grant and
    # we hide the section so reviewer identities don't leak
    # after the window has explicitly shut.
    after_release_closed_explicitly = (
        lifecycle.is_response_release_window_closed_explicitly(
            review_session
        )
    )

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )

    # Per-instrument visibility resolution. Two gates:
    #
    # - **Structure gate** (``instrument_mode``): does the
    #   operator's reviewee policy have ``raw``, ``anonymized``,
    #   or ``summarized`` authored on any window? If yes, the
    #   section renders.
    # - **Value gate** (``instrument_values_visible``): is the
    #   relevant window currently open? Only then do submitted
    #   values surface in the cells. When the window is closed
    #   (operator authored a mode but hasn't set / hasn't reached
    #   ``responses_release_at``), Raw + Anonymized sections
    #   still render the reviewer-row scaffolding with muted-
    #   empty value cells; Summarized sections skip rendering
    #   entirely because the aggregate has nothing to show without
    #   underlying values.
    #
    # ``anonymized`` (the operator-facing "Anonymized responses"
    # chip) renders the same per-reviewer table shape as Raw —
    # but every identification cell (Reviewer name + email + any
    # display-field cell) is replaced with the muted em-dash so
    # the reviewee can read the values without learning who said
    # what. ``summarized`` (the "Anonymized summaries" chip) is
    # a different render shape — one summary row with per-field
    # aggregates. The section's ``mode`` carries the picked mode
    # through to the template's per-cell branch.
    _RENDERED_MODES = {"raw", "anonymized", "summarized"}
    instrument_mode: dict[int, str] = {}
    instrument_values_visible: dict[int, bool] = {}
    for instrument in instruments:
        policy_rows = visibility_policies.list_for_instrument(
            db, instrument.id
        )
        policy = policy_rows.get("reviewee")
        if policy is None:
            continue
        while_mode = visibility_policies.decode_pair_to_mode(
            policy.while_ongoing_granularity,
            policy.while_ongoing_identification,
        )
        after_mode = visibility_policies.decode_pair_to_mode(
            policy.after_release_granularity,
            policy.after_release_identification,
        )
        authored_modes = {m for m in (while_mode, after_mode) if m}
        # ``raw`` wins when co-authored alongside ``anonymized`` /
        # ``summarized`` on different windows — Raw is the most
        # permissive rendering, the operator opted in to it for
        # at least one window, and the value gate below picks
        # whichever mode the open window carries. ``anonymized``
        # likewise beats ``summarized`` (more cell-level detail).
        if "raw" in authored_modes:
            picked_mode = "raw"
        elif "anonymized" in authored_modes:
            picked_mode = "anonymized"
        elif "summarized" in authored_modes:
            picked_mode = "summarized"
        else:
            continue
        # Once the operator has *explicitly closed* the after-
        # release window (``responses_release_until`` set and
        # reached — typically via the Stop release Operations
        # button or the scheduled close datetime), policy
        # authored only on after_release stops contributing to
        # the structure gate. Reviewer identities + display
        # fields must stop surfacing alongside the response
        # values they'd otherwise pair with. Pre-release (anchor
        # not yet set / not yet reached) stays a scaffolding-only
        # state — the operator gets the preview.
        if (
            after_mode in _RENDERED_MODES
            and while_mode not in _RENDERED_MODES
            and after_release_closed_explicitly
        ):
            continue
        instrument_mode[instrument.id] = picked_mode
        active_mode = visibility_policies.resolve_mode(
            policy,
            while_ongoing_open=while_ongoing_open,
            after_release_open=after_release_open,
        )
        instrument_values_visible[instrument.id] = (
            active_mode in _RENDERED_MODES
        )

    if not instrument_mode:
        return RevieweeResultsContext(
            session=review_session, sections=[]
        )

    # Assignment fan-out for the reviewee — every reviewer
    # assigned to review the signed-in reviewee on one of the
    # policy-opened instruments. Group-scoped instruments work
    # the same way: the response service fans a reviewer's
    # submission out to a row on every group member's assignment
    # row, so scoping to ``reviewee_id == reviewee.id`` already
    # picks up the reviewee's slice of any group-scoped grant
    # without widening the filter. Each ``(instrument_id,
    # reviewer_id)`` pair seeded here becomes a row in the
    # rendered table — even when no submitted response exists
    # yet for that pair, the row surfaces with the reviewer's
    # identity + empty value cells so the reviewee can see who
    # the would-be reviewers are.
    assignment_with_reviewer = list(
        db.execute(
            select(Assignment, Reviewer)
            .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
            .where(Assignment.session_id == review_session.id)
            .where(Assignment.reviewee_id == reviewee.id)
            .where(Assignment.include.is_(True))
            .where(Assignment.instrument_id.in_(instrument_mode.keys()))
        ).all()
    )

    # Visible display fields per instrument — excluding the
    # reviewee identity slots (Name / Email / Profile). Mirrors
    # the reviewer-surface render path's ``_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD``
    # filter so a tag column like ``reviewee.tag_1`` still
    # surfaces while the reviewee's own Name doesn't.
    from app.web.routes_reviewer._shared import (
        _NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD,
    )

    instrument_ids = set(instrument_mode.keys())
    display_fields_by_instrument: dict[
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

    pair_context = relationships_service.pair_context_lookup(
        db, review_session.id
    )

    # Seed the (instrument, reviewer) row set from the
    # assignment fan-out — every assigned reviewer surfaces a
    # row even when they haven't submitted yet. The display
    # cells are filled in below; the values cells fall back to
    # empty strings whenever no submitted response exists for a
    # given (instrument, reviewer, field) cell.
    reviewer_by_id: dict[int, Reviewer] = {}
    row_order: dict[int, list[int]] = {}
    representative_assignment: dict[tuple[int, int], Assignment] = {}
    for assignment, reviewer in assignment_with_reviewer:
        reviewer_by_id[reviewer.id] = reviewer
        rep_key = (assignment.instrument_id, reviewer.id)
        if rep_key not in representative_assignment:
            representative_assignment[rep_key] = assignment
        order_list = row_order.setdefault(assignment.instrument_id, [])
        if reviewer.id not in order_list:
            order_list.append(reviewer.id)

    # Pull every **submitted** response keyed about this
    # reviewee (or about a group this reviewee belongs to),
    # restricted to instruments where the value gate
    # (``instrument_values_visible``) is currently open. Same
    # join chain as the reviewer summary's, scope inverted to
    # ``Assignment.reviewee_id``. Draft rows
    # (``submitted_at IS NULL``) are excluded — the reviewer
    # identity still surfaces above, but the value cells stay
    # empty until the reviewer hits Submit AND the window opens.
    instrument_ids_with_values_visible = {
        iid
        for iid, visible in instrument_values_visible.items()
        if visible
    }
    if instrument_ids_with_values_visible:
        response_rows = list(
            db.execute(
                select(
                    Response,
                    Reviewer,
                    Instrument,
                    InstrumentResponseField,
                )
                .join(Assignment, Response.assignment_id == Assignment.id)
                .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
                .join(Instrument, Assignment.instrument_id == Instrument.id)
                .join(
                    InstrumentResponseField,
                    Response.response_field_id == InstrumentResponseField.id,
                )
                .where(Assignment.session_id == review_session.id)
                .where(Assignment.reviewee_id == reviewee.id)
                .where(Assignment.include.is_(True))
                .where(
                    Assignment.instrument_id.in_(
                        instrument_ids_with_values_visible
                    )
                )
                .where(Response.submitted_at.is_not(None))
            ).all()
        )
    else:
        response_rows = []

    # Index submitted values by (instrument_id, reviewer_id,
    # field_id). Group-scoped instruments fan out the same value
    # across every member's assignment row; the first occurrence
    # wins (they all carry the same value by the fan-out
    # invariant).
    cells: dict[tuple[int, int, int], str] = {}
    for response, reviewer, instrument, field in response_rows:
        cell_key = (instrument.id, reviewer.id, field.id)
        if cell_key in cells:
            continue
        cells[cell_key] = (
            response.value if response.value is not None else ""
        )

    sections: list[ResultsSection] = []
    total_instrument_count = len(instruments)
    for position, instrument in enumerate(instruments, start=1):
        if instrument.id not in instrument_mode:
            continue
        if instrument.id not in row_order:
            # Policy says Raw is OK and the window is open, but
            # no submitted responses exist yet. Skip the section
            # so the reviewee doesn't see an empty table card.
            continue
        is_group = instrument.group_kind is not None
        short_label = (instrument.short_label or "").strip()
        if total_instrument_count == 1:
            heading_title = short_label or instrument.name
        elif short_label:
            heading_title = f"#{position}: {short_label}"
        else:
            heading_title = f"#{position}"

        # Contract: for Raw + Anonymized modes, the table
        # columns must mirror the reviewer surface
        # (``review_surface.html``) for the same instrument —
        # the operator's column choices apply uniformly to
        # every reader. Specifically:
        #
        # - Response fields: same ``visible`` filter, same
        #   ``(order, id)`` sort, same per-data-type
        #   ``rs-narrow`` / ``rs-textlong`` class hints.
        # - Display fields: same ``visible`` filter, same
        #   ``_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD`` exclusion
        #   (Name / Email / Profile dropped — they'd repeat the
        #   signed-in reviewee on every row), same
        #   ``(order, id)`` sort.
        # - Per-column pixel widths from ``Instrument.column_widths``
        #   (``"identity"`` / ``"df_<id>"`` / ``"rf_<id>"``).
        #   When any custom width is set, the template emits a
        #   ``<colgroup>`` + ``table-layout: fixed`` so the
        #   widths actually take effect — same path the
        #   reviewer surface uses.
        #
        # Operators who drag-resize a column on the Band 2
        # editor get the same column width on the reviewee
        # results page; operators who select / deselect a
        # response or display field get the same column
        # set. Mirroring this contract lets the operator
        # configure once and have it apply across surfaces.
        fields = sorted(
            (f for f in instrument.response_fields if f.visible),
            key=lambda f: (f.order, f.id),
        )
        # Group-scoped instruments drop display field columns
        # entirely — the reviewer surface (``review_surface.html``)
        # + the reviewer summary (``_reviewer_summary.py``) do the
        # same, on the rationale that the per-row identity for a
        # group-scoped instrument is the GROUP, not individual
        # reviewees. Carrying per-reviewee tag / profile-link
        # columns alongside a group row would fan the identity
        # axis out into 4-5 distinct columns and lose the table's
        # row-per-reviewer shape. The reviewee surface mirrors
        # this — for a group-scoped instrument, only the
        # Reviewer identity column + the response field columns
        # render.
        instrument_display_fields = (
            []
            if is_group
            else display_fields_by_instrument.get(instrument.id, [])
        )
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

        picked_mode = instrument_mode[instrument.id]
        section_rows: list[ResultsRow] = []
        summarized_row: SummarizedRow | None = None
        if picked_mode == "summarized":
            # Collapse identification + rows into a single
            # aggregate row. Identity cell carries the two
            # counts; field cells carry per-data-type aggregates
            # (see :class:`SummarizedFieldCell`). The display-
            # field column list is dropped from the rendered
            # table — per spec the identification columns
            # collapse into the counts cell.
            reviewers_assigned = len(row_order[instrument.id])
            reviewers_with_responses = len(
                {
                    rid
                    for (iid, rid, _fid), value in cells.items()
                    if iid == instrument.id and (value or "").strip()
                }
            )
            field_cells: list[SummarizedFieldCell] = []
            for f in fields:
                raw_values = [
                    (
                        cells.get((instrument.id, rid, f.id), "")
                        or ""
                    ).strip()
                    for rid in row_order[instrument.id]
                ]
                raw_values = [v for v in raw_values if v]
                field_cells.append(
                    _summarize_field(f, raw_values)
                )
            summarized_row = SummarizedRow(
                reviewers_assigned=reviewers_assigned,
                reviewers_with_responses=reviewers_with_responses,
                field_cells=field_cells,
            )
            # Summarized mode ignores operator-set column widths
            # — the aggregate-row shape doesn't carry the same
            # column semantics, so pinning a Band 2 pixel width
            # to it would mis-apply.
            display_field_cols = []
            identity_width_px = None
            has_custom_widths = False
        else:
            # Sort rows by reviewer name so the reading order is
            # stable + alphabetical.
            ordered_reviewer_ids = sorted(
                row_order[instrument.id],
                key=lambda rid: (
                    (reviewer_by_id[rid].name or "").lower(),
                    rid,
                ),
            )
            for reviewer_id in ordered_reviewer_ids:
                reviewer = reviewer_by_id[reviewer_id]
                values = [
                    cells.get((instrument.id, reviewer_id, f.id), "")
                    for f in fields
                ]
                display_cells: list[SummaryDisplayCell] = []
                assignment = representative_assignment.get(
                    (instrument.id, reviewer_id)
                )
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
                    ResultsRow(
                        reviewer_name=reviewer.name or "",
                        reviewer_email=reviewer.email or None,
                        display_cells=display_cells,
                        values=values,
                    )
                )

        sections.append(
            ResultsSection(
                heading_title=heading_title,
                position=position,
                is_group=is_group,
                display_field_cols=display_field_cols,
                field_cols=field_cols,
                rows=section_rows,
                identity_width_px=identity_width_px,
                has_custom_widths=has_custom_widths,
                mode=picked_mode,
                summarized_row=summarized_row,
            )
        )

    return RevieweeResultsContext(
        session=review_session, sections=sections
    )


__all__ = [
    "GROUP_MEMBER_NAME_LIMIT",
    "RevieweeResultsContext",
    "ResultsRow",
    "ResultsSection",
    "SummarizedFieldCell",
    "SummarizedRow",
    "SummaryDisplayCell",
    "SummaryDisplayCol",
    "SummaryFieldCol",
    "SummaryGroupIdentity",
    "build_reviewee_results_context",
]
