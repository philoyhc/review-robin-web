"""Entity *metadata* extracts — backs the Extract data tab's
Reviewer / Reviewee response metadata cards.

These are response-activity rollups, one row per reviewer (or
reviewee). The column shape is driven by the operator's chip
selection on the card:

* **No instruments selected** — only the two cross-instrument
  totals ship: ``Assigned`` (the number of reviewee × field cells
  the reviewer is supposed to fill in across **every** instrument
  on the session) and ``Count`` (the number of those cells that
  have a non-empty response).
* **One or more instruments selected** — the same two totals,
  scoped to the selected instruments, followed by one
  **per-(instrument, field)** block per selected instrument. Each
  block always carries ``.Assigned`` + ``.Count``. Numeric fields
  (Integer / Decimal) add ``.Mean``, ``.Median``, ``.Min``,
  ``.Max``. String fields add ``.Length`` (the sum of characters
  across non-empty responses).

The per-block column prefix mirrors the By-instrument card's chip
label exactly: ``#{N}: {short_label}.{field}`` where ``{N}`` is
the instrument's 1-based session position (stable as chips
toggle) and ``{short_label}`` falls back to ``Instrument_{N}``
when the operator left it blank.

The ``all_*`` toggle gates which roster entries get a row:

* **On** — every reviewer / reviewee on the session roster.
* **Off** — only reviewers / reviewees who produced at least one
  non-empty response on any field of the in-scope instruments
  (the selected ones, or every instrument when nothing is
  selected).

Group-scoped instruments fan responses across every member
assignment at save time. The two sides handle that asymmetry
the same way ``entity_stats_extract.py`` does:

* **Reviewer side** — a reviewer fills one form per group, not
  one per member; the save layer copies the answer onto every
  member-assignment. So ``Assigned`` counts ``# groups × # fields``
  (deduped by ``(reviewer, instrument, group_key)``), and
  ``Count`` / per-field aggregates count each group answer once
  (deduped by ``(reviewer, group_key, field_id)``).
* **Reviewee side** — from a reviewee's perspective there is
  exactly one cell per (reviewer, field) about them, so no
  dedupe is needed; each member-assignment counts on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import responses as responses_service

__all__ = [
    "build_reviewer_metadata",
    "build_reviewee_metadata",
    "compute_self_review_data_state",
    "SELF_REVIEW_HANDLING_STATES",
    "SELF_REVIEW_HANDLING_DEFAULT",
    "self_review_handling_filename_suffix",
]


_NUMERIC = ("Integer", "Decimal")


# Self-review handling chip — three-state machine documented in
# ``guide/extract_data.md`` § *Self-review handling in summarizing
# extracts*. The aggregate-fold rule reads the canonical
# ``Assignment.is_self_review`` column landed by the consolidation
# slice (``guide/archive/self_review_consolidate.md``).
SELF_REVIEW_HANDLING_STATES: tuple[str, str, str] = (
    "include_self",
    "exclude_self",
    "both",
)
SELF_REVIEW_HANDLING_DEFAULT = "include_self"
_SUFFIX_BY_STATE: dict[str, str] = {
    "include_self": "_self",
    "exclude_self": "_noself",
}


def self_review_handling_filename_suffix(state: str) -> str:
    """Per-state filename suffix appended before the ``.csv``
    extension on the metadata downloads. ``include_self`` → ``_self``,
    ``exclude_self`` → ``_noself``, ``both`` → ``_both`` per the
    chip's Q1 / Q2 resolutions."""
    if state == "both":
        return "_both"
    return _SUFFIX_BY_STATE.get(state, "_self")


def compute_self_review_data_state(
    db: Session,
    *,
    session_id: int,
    instrument_ids: set[int] | None = None,
) -> dict[str, bool]:
    """Server-side preflight for the chip's locked / selectable
    state. Returns ``{'has_self': bool, 'has_noself': bool}`` for
    the active scope.

    ``instrument_ids=None`` ↔ the operator hasn't picked any
    instrument chips — scope spans every session instrument (the
    same shape ``_resolve_scope`` uses for the totals-only header).
    """
    base = [
        Assignment.session_id == session_id,
        Assignment.include.is_(True),
    ]
    if instrument_ids:
        base.append(Assignment.instrument_id.in_(instrument_ids))
    has_self = (
        db.execute(
            select(Assignment.id).where(
                *base, Assignment.is_self_review.is_(True)
            ).limit(1)
        ).scalar()
        is not None
    )
    has_noself = (
        db.execute(
            select(Assignment.id).where(
                *base, Assignment.is_self_review.is_(False)
            ).limit(1)
        ).scalar()
        is not None
    )
    return {"has_self": has_self, "has_noself": has_noself}


def _column_suffix(state: str) -> str:
    """Per-column header suffix for the totals + per-field blocks
    on a single-state extract. ``both`` is handled by composing two
    single-state passes upstream; the suffix here always reflects
    the single state being rendered."""
    return _SUFFIX_BY_STATE.get(state, "_self")


# --------------------------------------------------------------------------- #
# Header composition
# --------------------------------------------------------------------------- #


@dataclass
class _FieldSpec:
    """One response field's metadata-extract footprint."""

    field_id: int
    data_type: str | None
    column_prefix: str  # e.g. "#2: Peer.Strengths"

    @property
    def is_numeric(self) -> bool:
        return self.data_type in _NUMERIC

    @property
    def is_string(self) -> bool:
        return self.data_type == "String"

    def columns(self) -> list[str]:
        cols = [
            f"{self.column_prefix}.Assigned",
            f"{self.column_prefix}.Count",
        ]
        if self.is_numeric:
            cols.extend(
                (
                    f"{self.column_prefix}.Mean",
                    f"{self.column_prefix}.Median",
                    f"{self.column_prefix}.Min",
                    f"{self.column_prefix}.Max",
                )
            )
        elif self.is_string:
            cols.append(f"{self.column_prefix}.Length")
        return cols


def _instrument_short_or_fallback(
    instrument: Instrument, position: int
) -> str:
    short = (instrument.short_label or "").strip()
    return short or f"Instrument_{position}"


def _resolve_scope(
    db: Session,
    review_session: ReviewSession,
    instrument_ids: set[int] | None,
) -> tuple[
    list[_FieldSpec],
    set[int],
    dict[int, list[InstrumentResponseField]],
    dict[int, InstrumentResponseField],
]:
    """Normalise the chip selection into the data the row builder
    needs.

    Returns ``(field_specs, scope_instrument_ids,
    fields_by_instrument, field_by_id)``.

    * ``field_specs`` is empty when ``instrument_ids is None`` (no
      per-field blocks ship); otherwise it carries one spec per
      response field on each selected instrument in session order.
    * ``scope_instrument_ids`` is the set the totals scan — either
      the selected ids, or every session instrument's id when
      nothing is selected.
    * ``fields_by_instrument`` / ``field_by_id`` are convenience
      lookups for the assignment / response loops.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )

    scope_ids: set[int] = (
        set(instrument_ids)
        if instrument_ids is not None
        else {i.id for i in instruments}
    )

    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    field_by_id: dict[int, InstrumentResponseField] = {}
    for instrument in instruments:
        if instrument.id not in scope_ids:
            continue
        ordered_fields = sorted(
            instrument.response_fields, key=lambda f: (f.order, f.id)
        )
        fields_by_instrument[instrument.id] = ordered_fields
        for f in ordered_fields:
            field_by_id[f.id] = f

    specs: list[_FieldSpec] = []
    if instrument_ids is not None:
        for position, instrument in enumerate(instruments, start=1):
            if instrument.id not in scope_ids:
                continue
            short_label = _instrument_short_or_fallback(instrument, position)
            prefix = f"#{position}: {short_label}"
            for f in fields_by_instrument[instrument.id]:
                specs.append(
                    _FieldSpec(
                        field_id=f.id,
                        data_type=f._inline_data_type,
                        column_prefix=f"{prefix}.{f.label or f.field_key}",
                    )
                )
    return specs, scope_ids, fields_by_instrument, field_by_id


# --------------------------------------------------------------------------- #
# Accumulator
# --------------------------------------------------------------------------- #


@dataclass
class _FieldAcc:
    """One field's accumulator for a single entity."""

    numeric_values: list[float] = dc_field(default_factory=list)
    string_chars: int = 0
    string_count: int = 0
    other_count: int = 0

    @property
    def count(self) -> int:
        return self.string_count + self.other_count + len(self.numeric_values)


def _ingest_value(
    acc: _FieldAcc,
    field: InstrumentResponseField | None,
    value: str,
) -> None:
    data_type = field._inline_data_type if field is not None else None
    if data_type in _NUMERIC:
        try:
            acc.numeric_values.append(float(value))
        except (TypeError, ValueError):
            acc.other_count += 1
    elif data_type == "String":
        acc.string_count += 1
        acc.string_chars += len(value)
    else:
        acc.other_count += 1


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _field_columns(
    spec: _FieldSpec,
    per_field_assigned: dict[int, int],
    per_field_acc: dict[int, _FieldAcc],
) -> list[str]:
    assigned = per_field_assigned.get(spec.field_id, 0)
    acc = per_field_acc.get(spec.field_id, _FieldAcc())
    cols = [str(assigned), str(acc.count)]
    if spec.is_numeric:
        if acc.numeric_values:
            cols.extend(
                (
                    _format_number(mean(acc.numeric_values)),
                    _format_number(median(acc.numeric_values)),
                    _format_number(min(acc.numeric_values)),
                    _format_number(max(acc.numeric_values)),
                )
            )
        else:
            cols.extend(("", "", "", ""))
    elif spec.is_string:
        cols.append(str(acc.string_chars))
    return cols


# --------------------------------------------------------------------------- #
# Reviewer side
# --------------------------------------------------------------------------- #


# Identity columns only — ``Assigned`` and ``Count`` are part
# of the per-state data block now (PR A of the Self-review
# handling chip slice, per Q1 of ``guide/extract_data.md`` §
# *Self-review handling*). The per-state block carries
# ``Assigned_self``/``Count_self`` or ``Assigned_noself``/
# ``Count_noself`` so the denominators stay honest under
# self/no-self filtering.
_REVIEWER_BASE_HEADER: tuple[str, ...] = (
    "ReviewerName",
    "ReviewerEmail",
)


def _reviewer_state_block(
    db: Session,
    review_session: ReviewSession,
    *,
    state: str,
    field_specs: list[_FieldSpec],
    scope_ids: set[int],
    fields_by_instrument: dict[int, list[InstrumentResponseField]],
    field_by_id: dict[int, InstrumentResponseField],
    reviewers: list[Reviewer],
) -> tuple[tuple[str, ...], dict[int, list[str]], dict[int, int]]:
    """One Self-review handling state's worth of data columns for
    the reviewer side. Returns ``(header_cols, body_by_reviewer,
    total_count_by_reviewer)``.

    ``state="include_self"`` rolls every ``include=True`` row in
    (suffix ``_self``); ``"exclude_self"`` filters
    ``Assignment.is_self_review = False`` (suffix ``_noself``). The
    ``both`` state composes two passes upstream; this function
    handles one pass at a time.
    """
    selected_field_ids = {spec.field_id for spec in field_specs}
    suffix = _column_suffix(state)
    exclude_self = state == "exclude_self"

    assigned_per_field: dict[int, dict[int, int]] = {
        r.id: {spec.field_id: 0 for spec in field_specs} for r in reviewers
    }
    total_assigned: dict[int, int] = {r.id: 0 for r in reviewers}
    response_acc: dict[int, dict[int, _FieldAcc]] = {
        r.id: {spec.field_id: _FieldAcc() for spec in field_specs}
        for r in reviewers
    }
    total_count: dict[int, int] = {r.id: 0 for r in reviewers}

    if scope_ids:
        assignment_filter = [
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Assignment.instrument_id.in_(scope_ids),
        ]
        if exclude_self:
            assignment_filter.append(Assignment.is_self_review.is_(False))
        assignments = list(
            db.execute(select(Assignment).where(*assignment_filter)).scalars()
        )
        group_key_by_assignment = responses_service.group_keys(
            db, assignments=assignments, session_id=review_session.id
        )

        # Reviewer-side Assigned dedupes group fan-out: a reviewer
        # fills one form per group, not one per member, so each
        # ``(reviewer, instrument, group_key)`` triple counts once.
        seen_reviewer_group_assigned: set[
            tuple[int, int, tuple[str, ...]]
        ] = set()
        for a in assignments:
            if a.reviewer_id not in total_assigned:
                continue
            group_key = group_key_by_assignment.get(a.id)
            if group_key is not None:
                dedupe_key = (a.reviewer_id, a.instrument_id, group_key)
                if dedupe_key in seen_reviewer_group_assigned:
                    continue
                seen_reviewer_group_assigned.add(dedupe_key)
            per_field = assigned_per_field[a.reviewer_id]
            for f in fields_by_instrument.get(a.instrument_id, ()):
                total_assigned[a.reviewer_id] += 1
                if f.id in selected_field_ids:
                    per_field[f.id] += 1

        # Reviewer-side Count + per-field rollup dedupe the same
        # way: each group answer counts once per (reviewer,
        # group_key, field_id).
        seen_reviewer_group_response: set[
            tuple[int, tuple[str, ...], int]
        ] = set()
        response_filter = [
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Assignment.instrument_id.in_(scope_ids),
        ]
        if exclude_self:
            response_filter.append(Assignment.is_self_review.is_(False))
        for assignment_id, reviewer_id, field_id, value in db.execute(
            select(
                Assignment.id,
                Assignment.reviewer_id,
                Response.response_field_id,
                Response.value,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(*response_filter)
        ):
            if reviewer_id not in total_count or not value:
                continue
            group_key = group_key_by_assignment.get(assignment_id)
            if group_key is not None:
                dedupe_key = (reviewer_id, group_key, field_id)
                if dedupe_key in seen_reviewer_group_response:
                    continue
                seen_reviewer_group_response.add(dedupe_key)
            total_count[reviewer_id] += 1
            if field_id in selected_field_ids:
                _ingest_value(
                    response_acc[reviewer_id][field_id],
                    field_by_id.get(field_id),
                    value,
                )

    header_cols: tuple[str, ...] = (
        f"Assigned{suffix}",
        f"Count{suffix}",
    ) + tuple(f"{col}{suffix}" for spec in field_specs for col in spec.columns())
    body_by_reviewer: dict[int, list[str]] = {}
    for r in reviewers:
        body: list[str] = [
            str(total_assigned[r.id]),
            str(total_count[r.id]),
        ]
        for spec in field_specs:
            body.extend(
                _field_columns(
                    spec,
                    assigned_per_field[r.id],
                    response_acc[r.id],
                )
            )
        body_by_reviewer[r.id] = body
    return header_cols, body_by_reviewer, total_count


def build_reviewer_metadata(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument_ids: set[int] | None,
    all_reviewers: bool,
    self_review_handling: str = SELF_REVIEW_HANDLING_DEFAULT,
) -> list[tuple[str, ...]]:
    """Return the rows (header + body) for the Reviewer response
    metadata CSV.

    ``instrument_ids`` of ``None`` ships only the two
    cross-instrument totals (scanning every session instrument).
    A non-empty set ships per-(instrument, field) blocks after the
    totals; the totals themselves are scoped to the same set so
    column denominators line up.

    ``all_reviewers`` False filters body rows to reviewers with at
    least one non-empty response on any in-scope field. On the
    ``both`` state a reviewer survives the filter when EITHER the
    self pool or the non-self pool carries at least one response.

    ``self_review_handling`` ∈ ``{"include_self", "exclude_self",
    "both"}`` per the Self-review handling chip. Drives the
    column-name suffix (``_self`` / ``_noself``) and, on
    ``exclude_self`` / ``both``, the ``WHERE NOT is_self_review``
    filter on the per-state pool. See ``guide/extract_data.md``
    § *Self-review handling in summarizing extracts*.
    """
    if self_review_handling not in SELF_REVIEW_HANDLING_STATES:
        self_review_handling = SELF_REVIEW_HANDLING_DEFAULT
    states_to_run: tuple[str, ...] = (
        ("include_self", "exclude_self")
        if self_review_handling == "both"
        else (self_review_handling,)
    )

    field_specs, scope_ids, fields_by_instrument, field_by_id = _resolve_scope(
        db, review_session, instrument_ids
    )
    reviewers = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(
                (Reviewer.status != "active").asc(),
                Reviewer.name,
                Reviewer.email,
            )
        ).scalars()
    )

    state_blocks: list[
        tuple[tuple[str, ...], dict[int, list[str]], dict[int, int]]
    ] = []
    for state in states_to_run:
        state_blocks.append(
            _reviewer_state_block(
                db,
                review_session,
                state=state,
                field_specs=field_specs,
                scope_ids=scope_ids,
                fields_by_instrument=fields_by_instrument,
                field_by_id=field_by_id,
                reviewers=reviewers,
            )
        )

    header: tuple[str, ...] = _REVIEWER_BASE_HEADER + tuple(
        col for header_cols, _, _ in state_blocks for col in header_cols
    )
    rows: list[tuple[str, ...]] = [header]
    for r in reviewers:
        if not all_reviewers and not any(
            total_count[r.id] > 0 for _, _, total_count in state_blocks
        ):
            continue
        body: list[str] = [r.name, r.email]
        for _, body_by_reviewer, _ in state_blocks:
            body.extend(body_by_reviewer[r.id])
        rows.append(tuple(body))
    return rows


# --------------------------------------------------------------------------- #
# Reviewee side — symmetric
# --------------------------------------------------------------------------- #


_REVIEWEE_BASE_HEADER: tuple[str, ...] = (
    "RevieweeName",
    "RevieweeEmail",
)


def _reviewee_state_block(
    db: Session,
    review_session: ReviewSession,
    *,
    state: str,
    field_specs: list[_FieldSpec],
    scope_ids: set[int],
    fields_by_instrument: dict[int, list[InstrumentResponseField]],
    field_by_id: dict[int, InstrumentResponseField],
    reviewees: list[Reviewee],
) -> tuple[tuple[str, ...], dict[int, list[str]], dict[int, int]]:
    """Symmetric to :func:`_reviewer_state_block` — one Self-
    review handling state's data block for the reviewee side."""
    selected_field_ids = {spec.field_id for spec in field_specs}
    suffix = _column_suffix(state)
    exclude_self = state == "exclude_self"

    assigned_per_field: dict[int, dict[int, int]] = {
        e.id: {spec.field_id: 0 for spec in field_specs} for e in reviewees
    }
    total_assigned: dict[int, int] = {e.id: 0 for e in reviewees}
    response_acc: dict[int, dict[int, _FieldAcc]] = {
        e.id: {spec.field_id: _FieldAcc() for spec in field_specs}
        for e in reviewees
    }
    total_count: dict[int, int] = {e.id: 0 for e in reviewees}

    if scope_ids:
        assignment_filter = [
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Assignment.instrument_id.in_(scope_ids),
        ]
        if exclude_self:
            assignment_filter.append(Assignment.is_self_review.is_(False))
        for reviewee_id, instrument_id in db.execute(
            select(
                Assignment.reviewee_id, Assignment.instrument_id
            ).where(*assignment_filter)
        ):
            if reviewee_id not in total_assigned:
                continue
            per_field = assigned_per_field[reviewee_id]
            for f in fields_by_instrument.get(instrument_id, ()):
                total_assigned[reviewee_id] += 1
                if f.id in selected_field_ids:
                    per_field[f.id] += 1

        response_filter = [
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Assignment.instrument_id.in_(scope_ids),
        ]
        if exclude_self:
            response_filter.append(Assignment.is_self_review.is_(False))
        for reviewee_id, field_id, value in db.execute(
            select(
                Assignment.reviewee_id,
                Response.response_field_id,
                Response.value,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(*response_filter)
        ):
            if reviewee_id not in total_count or not value:
                continue
            total_count[reviewee_id] += 1
            if field_id in selected_field_ids:
                _ingest_value(
                    response_acc[reviewee_id][field_id],
                    field_by_id.get(field_id),
                    value,
                )

    header_cols: tuple[str, ...] = (
        f"Assigned{suffix}",
        f"Count{suffix}",
    ) + tuple(f"{col}{suffix}" for spec in field_specs for col in spec.columns())
    body_by_reviewee: dict[int, list[str]] = {}
    for e in reviewees:
        body: list[str] = [
            str(total_assigned[e.id]),
            str(total_count[e.id]),
        ]
        for spec in field_specs:
            body.extend(
                _field_columns(
                    spec,
                    assigned_per_field[e.id],
                    response_acc[e.id],
                )
            )
        body_by_reviewee[e.id] = body
    return header_cols, body_by_reviewee, total_count


def build_reviewee_metadata(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument_ids: set[int] | None,
    all_reviewees: bool,
    self_review_handling: str = SELF_REVIEW_HANDLING_DEFAULT,
) -> list[tuple[str, ...]]:
    """Return the rows (header + body) for the Reviewee response
    metadata CSV — symmetric to ``build_reviewer_metadata``.

    ``self_review_handling`` ∈ ``{"include_self", "exclude_self",
    "both"}`` per the chip's state machine; see
    :func:`build_reviewer_metadata` for the contract.
    """
    if self_review_handling not in SELF_REVIEW_HANDLING_STATES:
        self_review_handling = SELF_REVIEW_HANDLING_DEFAULT
    states_to_run: tuple[str, ...] = (
        ("include_self", "exclude_self")
        if self_review_handling == "both"
        else (self_review_handling,)
    )

    field_specs, scope_ids, fields_by_instrument, field_by_id = _resolve_scope(
        db, review_session, instrument_ids
    )
    reviewees = list(
        db.execute(
            select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .order_by(
                (Reviewee.status != "active").asc(),
                Reviewee.name,
                Reviewee.email_or_identifier,
            )
        ).scalars()
    )

    state_blocks: list[
        tuple[tuple[str, ...], dict[int, list[str]], dict[int, int]]
    ] = []
    for state in states_to_run:
        state_blocks.append(
            _reviewee_state_block(
                db,
                review_session,
                state=state,
                field_specs=field_specs,
                scope_ids=scope_ids,
                fields_by_instrument=fields_by_instrument,
                field_by_id=field_by_id,
                reviewees=reviewees,
            )
        )

    header: tuple[str, ...] = _REVIEWEE_BASE_HEADER + tuple(
        col for header_cols, _, _ in state_blocks for col in header_cols
    )
    rows: list[tuple[str, ...]] = [header]
    for e in reviewees:
        if not all_reviewees and not any(
            total_count[e.id] > 0 for _, _, total_count in state_blocks
        ):
            continue
        body: list[str] = [e.name, e.email_or_identifier]
        for _, body_by_reviewee, _ in state_blocks:
            body.extend(body_by_reviewee[e.id])
        rows.append(tuple(body))
    return rows
