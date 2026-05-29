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
]


_NUMERIC = ("Integer", "Decimal")


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


_REVIEWER_BASE_HEADER: tuple[str, ...] = (
    "ReviewerName",
    "ReviewerEmail",
    "Assigned",
    "Count",
)


def build_reviewer_metadata(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument_ids: set[int] | None,
    all_reviewers: bool,
) -> list[tuple[str, ...]]:
    """Return the rows (header + body) for the Reviewer response
    metadata CSV.

    ``instrument_ids`` of ``None`` ships only the two
    cross-instrument totals (scanning every session instrument).
    A non-empty set ships per-(instrument, field) blocks after the
    totals; the totals themselves are scoped to the same set so
    column denominators line up.

    ``all_reviewers`` False filters body rows to reviewers with at
    least one non-empty response on any in-scope field.
    """
    field_specs, scope_ids, fields_by_instrument, field_by_id = _resolve_scope(
        db, review_session, instrument_ids
    )
    selected_field_ids = {spec.field_id for spec in field_specs}

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
        assignments = list(
            db.execute(
                select(Assignment).where(
                    Assignment.session_id == review_session.id,
                    Assignment.include.is_(True),
                    Assignment.instrument_id.in_(scope_ids),
                )
            ).scalars()
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
        for assignment_id, reviewer_id, field_id, value in db.execute(
            select(
                Assignment.id,
                Assignment.reviewer_id,
                Response.response_field_id,
                Response.value,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
                Assignment.instrument_id.in_(scope_ids),
            )
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

    header: tuple[str, ...] = _REVIEWER_BASE_HEADER + tuple(
        col for spec in field_specs for col in spec.columns()
    )
    rows: list[tuple[str, ...]] = [header]
    for r in reviewers:
        if not all_reviewers and total_count[r.id] == 0:
            continue
        body: list[str] = [
            r.name,
            r.email,
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
        rows.append(tuple(body))
    return rows


# --------------------------------------------------------------------------- #
# Reviewee side — symmetric
# --------------------------------------------------------------------------- #


_REVIEWEE_BASE_HEADER: tuple[str, ...] = (
    "RevieweeName",
    "RevieweeEmail",
    "Assigned",
    "Count",
)


def build_reviewee_metadata(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument_ids: set[int] | None,
    all_reviewees: bool,
) -> list[tuple[str, ...]]:
    """Return the rows (header + body) for the Reviewee response
    metadata CSV — symmetric to ``build_reviewer_metadata``."""
    field_specs, scope_ids, fields_by_instrument, field_by_id = _resolve_scope(
        db, review_session, instrument_ids
    )
    selected_field_ids = {spec.field_id for spec in field_specs}

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
        for reviewee_id, instrument_id in db.execute(
            select(
                Assignment.reviewee_id, Assignment.instrument_id
            ).where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
                Assignment.instrument_id.in_(scope_ids),
            )
        ):
            if reviewee_id not in total_assigned:
                continue
            per_field = assigned_per_field[reviewee_id]
            for f in fields_by_instrument.get(instrument_id, ()):
                total_assigned[reviewee_id] += 1
                if f.id in selected_field_ids:
                    per_field[f.id] += 1

        for reviewee_id, field_id, value in db.execute(
            select(
                Assignment.reviewee_id,
                Response.response_field_id,
                Response.value,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
                Assignment.instrument_id.in_(scope_ids),
            )
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

    header: tuple[str, ...] = _REVIEWEE_BASE_HEADER + tuple(
        col for spec in field_specs for col in spec.columns()
    )
    rows: list[tuple[str, ...]] = [header]
    for e in reviewees:
        if not all_reviewees and total_count[e.id] == 0:
            continue
        body: list[str] = [
            e.name,
            e.email_or_identifier,
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
        rows.append(tuple(body))
    return rows
