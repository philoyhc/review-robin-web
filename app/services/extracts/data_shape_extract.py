"""Data shape extract — turn a saved ``DataShape`` row into a
CSV per the row-key contract in ``spec/extract_data.md``
"Row-key contract — for the file-gen wiring slice".

Row scheme depends on the column-chip selection on the shape:

* **Per-individual** — when ``{axis}:name`` or ``{axis}:email``
  is among the selected slots. One row per reviewer / reviewee
  on the session.
* **Per-tag-combo** — when no name / email is selected but at
  least one tag chip is. One row per distinct tag-combination,
  aggregating over the individuals sharing that combination.
* **Single summary row** — when no identification chip is
  selected. One row across the whole roster.

Scope chips on the saved shape narrow what "in-scope
responses" mean for the aggregate columns:

* ``instrument_id`` null → aggregates span every instrument.
* ``instrument_id`` set + ``response_field_id`` null → scope
  to that instrument's fields.
* ``response_field_id`` set → scope to that single field.

Group-scoped instruments inherit the asymmetric dedupe rule
from ``entity_metadata_extract`` — reviewer side dedupes by
``(reviewer-tag-combo-or-individual, group_key, field_id)``;
reviewee side does not.

The shipped fan-out chips (``list-items`` / ``discrete-steps``)
emit one CSV column per option / step value when selected; the
column header uses the option / step label and the cell carries
the count of in-scope responses matching that value.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    DataShape,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import field_labels
from app.services import responses as responses_service


__all__ = ["build_shape_rows"]


_NUMERIC = ("Integer", "Decimal")
_TAG_SLOTS = ("tag-1", "tag-2", "tag-3")


# --------------------------------------------------------------------------- #
# Per-entity accumulator
# --------------------------------------------------------------------------- #


@dataclass
class _Acc:
    """One row's running aggregate state."""

    assigned: int = 0
    numeric_values: list[float] = dc_field(default_factory=list)
    string_chars: int = 0
    string_count: int = 0
    other_count: int = 0
    # ``data-shape-field-list-options`` / ``...-discrete-steps``
    # fan-out: count of non-empty responses matching each
    # discrete value. Keyed by the value's string form.
    fanout_counts: dict[str, int] = dc_field(default_factory=dict)

    @property
    def count(self) -> int:
        return self.string_count + self.other_count + len(self.numeric_values)


def _ingest(
    acc: _Acc, field: InstrumentResponseField | None, value: str
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
    # Fan-out counter: always track raw value counts so the
    # final header can emit a column per discrete value.
    if value:
        acc.fanout_counts[value] = acc.fanout_counts.get(value, 0) + 1


def _format_number(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return f"{v:g}"


# --------------------------------------------------------------------------- #
# Scope resolution
# --------------------------------------------------------------------------- #


@dataclass
class _Scope:
    instrument_ids: set[int]
    field_ids: set[int]
    field_by_id: dict[int, InstrumentResponseField]
    # The single anchor field (when the shape pinned one) —
    # used to drive ``list-items`` / ``discrete-steps`` fan-out
    # plus to label the numeric / string aggregate columns.
    anchor_field: InstrumentResponseField | None


def _resolve_scope(
    db: Session, review_session: ReviewSession, shape: DataShape
) -> _Scope:
    instruments = list(
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        ).scalars()
    )
    if shape.instrument_id is not None:
        instruments = [i for i in instruments if i.id == shape.instrument_id]
    instrument_ids = {i.id for i in instruments}

    field_by_id: dict[int, InstrumentResponseField] = {}
    for instrument in instruments:
        for f in instrument.response_fields:
            field_by_id[f.id] = f
    if shape.response_field_id is not None:
        field_by_id = {
            shape.response_field_id: field_by_id[shape.response_field_id]
        } if shape.response_field_id in field_by_id else {}
    field_ids = set(field_by_id.keys())
    anchor_field = (
        field_by_id.get(shape.response_field_id)
        if shape.response_field_id is not None
        else None
    )
    return _Scope(
        instrument_ids=instrument_ids,
        field_ids=field_ids,
        field_by_id=field_by_id,
        anchor_field=anchor_field,
    )


# --------------------------------------------------------------------------- #
# Header composition
# --------------------------------------------------------------------------- #


def _tag_header_label(
    review_session: ReviewSession, axis: str, tag_slot: str
) -> str:
    """``tag-1`` → ``Tag 1`` (or the operator-renamed label
    via ``field_labels.resolve``)."""
    slot_n = tag_slot.rsplit("-", 1)[-1]
    return field_labels.resolve(
        review_session, axis, f"tag_{slot_n}"
    )


def _discrete_step_values(
    field: InstrumentResponseField,
) -> list[str]:
    """Mirror of ``_extract_data._discrete_steps_values`` for
    the file-gen side — same arithmetic, returns the discrete
    step strings. Empty when the field doesn't qualify."""
    data_type = field._inline_data_type
    if data_type not in _NUMERIC:
        return []
    mn = field._inline_min
    mx = field._inline_max
    step = field._inline_step
    if step is None and data_type == "Integer":
        step = 1.0
    if mn is None or mx is None or step is None or step <= 0:
        return []
    span = mx - mn
    if span < 0:
        return []
    count = int(round(span / step)) + 1
    if count <= 0 or count > 12:
        return []
    is_int = data_type == "Integer"
    values: list[str] = []
    for i in range(count):
        v = mn + i * step
        if is_int or v == int(v):
            values.append(str(int(round(v))))
        else:
            values.append(f"{v:g}")
    return values


def _list_option_values(
    field: InstrumentResponseField,
) -> list[str]:
    csv = field._inline_list_csv or ""
    return [s.strip() for s in csv.split(",") if s.strip()]


# --------------------------------------------------------------------------- #
# Row composition
# --------------------------------------------------------------------------- #


def _entity_tuple_individual(
    axis: str, entity, slots: list[str]
) -> tuple[str, ...]:
    """Identification cells for a per-individual row."""
    cells: list[str] = []
    for slot in slots:
        if slot == f"{axis}:name":
            cells.append(entity.name)
        elif slot == f"{axis}:email":
            cells.append(
                entity.email
                if axis == "reviewer"
                else entity.email_or_identifier
            )
        elif slot.startswith(f"{axis}:tag-"):
            n = slot.rsplit("-", 1)[-1]
            attr = f"tag_{n}"
            cells.append(getattr(entity, attr, None) or "")
    return tuple(cells)


def _aggregate_cells(
    axis: str,
    slots: list[str],
    acc: _Acc,
    anchor_field: InstrumentResponseField | None,
) -> list[str]:
    """Aggregate cells for one row."""
    cells: list[str] = []
    for slot in slots:
        if slot == f"{axis}:assigned":
            cells.append(str(acc.assigned))
        elif slot == f"{axis}:count":
            cells.append(str(acc.count))
        elif slot == f"{axis}:mean":
            cells.append(
                _format_number(mean(acc.numeric_values))
                if acc.numeric_values
                else ""
            )
        elif slot == f"{axis}:median":
            cells.append(
                _format_number(median(acc.numeric_values))
                if acc.numeric_values
                else ""
            )
        elif slot == f"{axis}:min":
            cells.append(
                _format_number(min(acc.numeric_values))
                if acc.numeric_values
                else ""
            )
        elif slot == f"{axis}:max":
            cells.append(
                _format_number(max(acc.numeric_values))
                if acc.numeric_values
                else ""
            )
        elif slot == f"{axis}:length":
            cells.append(str(acc.string_chars))
        elif slot == f"{axis}:list-items":
            options = (
                _list_option_values(anchor_field)
                if anchor_field
                else []
            )
            for opt in options:
                cells.append(str(acc.fanout_counts.get(opt, 0)))
        elif slot == f"{axis}:discrete-steps":
            steps = (
                _discrete_step_values(anchor_field)
                if anchor_field
                else []
            )
            for step in steps:
                cells.append(str(acc.fanout_counts.get(step, 0)))
    return cells


def _compose_header(
    review_session: ReviewSession,
    axis: str,
    slots: list[str],
    anchor_field: InstrumentResponseField | None,
) -> tuple[str, ...]:
    """One header cell per identification slot + per
    aggregate slot. Fan-out slots expand to one cell per
    option / step value."""
    axis_title = "Reviewer" if axis == "reviewer" else "Reviewee"
    header: list[str] = []
    for slot in slots:
        if slot == f"{axis}:name":
            header.append(f"{axis_title}Name")
        elif slot == f"{axis}:email":
            header.append(f"{axis_title}Email")
        elif slot.startswith(f"{axis}:tag-"):
            header.append(_tag_header_label(review_session, axis, slot.split(":", 1)[1]))
        elif slot == f"{axis}:assigned":
            header.append("Assigned")
        elif slot == f"{axis}:count":
            header.append("Count")
        elif slot == f"{axis}:mean":
            header.append("Mean")
        elif slot == f"{axis}:median":
            header.append("Median")
        elif slot == f"{axis}:min":
            header.append("Min")
        elif slot == f"{axis}:max":
            header.append("Max")
        elif slot == f"{axis}:length":
            header.append("Length")
        elif slot == f"{axis}:list-items":
            options = (
                _list_option_values(anchor_field)
                if anchor_field
                else []
            )
            header.extend(options)
        elif slot == f"{axis}:discrete-steps":
            steps = (
                _discrete_step_values(anchor_field)
                if anchor_field
                else []
            )
            header.extend(steps)
    return tuple(header)


# --------------------------------------------------------------------------- #
# Main builder
# --------------------------------------------------------------------------- #


def _entity_tag_combo(axis: str, entity, selected_tag_slots: list[str]) -> tuple[str, ...]:
    parts: list[str] = []
    for slot in selected_tag_slots:
        n = slot.rsplit("-", 1)[-1]
        parts.append(getattr(entity, f"tag_{n}", None) or "")
    return tuple(parts)


def build_shape_rows(
    db: Session, review_session: ReviewSession, shape: DataShape
) -> list[tuple[str, ...]]:
    """Build the (header + body) row list for ``shape``'s CSV.

    Body row count + the chosen row scheme follow the
    spec/extract_data.md row-key contract; aggregate
    computations follow the same asymmetric dedupe rule the
    Reviewer / Reviewee response metadata cards already use.
    """
    slots: list[str] = json.loads(shape.column_chip_slots)
    axis = shape.axis
    assert axis in ("reviewer", "reviewee")
    scope = _resolve_scope(db, review_session, shape)

    has_name = f"{axis}:name" in slots
    has_email = f"{axis}:email" in slots
    selected_tag_slots = [
        s for s in slots if s.startswith(f"{axis}:tag-")
    ]
    per_individual = has_name or has_email
    per_tag_combo = bool(selected_tag_slots) and not per_individual

    EntityCls = Reviewer if axis == "reviewer" else Reviewee
    entities = list(
        db.execute(
            select(EntityCls).where(
                EntityCls.session_id == review_session.id
            )
        ).scalars()
    )

    # Group key resolver for the reviewer-side asymmetric
    # dedupe — when a group-scoped instrument fans an answer
    # across every member-assignment, the reviewer side
    # collapses them by ``(reviewer, group_key, field_id)``.
    assignments = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
                Assignment.instrument_id.in_(scope.instrument_ids)
                if scope.instrument_ids
                else Assignment.instrument_id.is_(None),
            )
        ).scalars()
    ) if scope.instrument_ids else []
    group_key_by_assignment = (
        responses_service.group_keys(
            db, assignments=assignments, session_id=review_session.id
        )
        if assignments
        else {}
    )
    fields_per_instrument: dict[int, list[int]] = {}
    for fid, fobj in scope.field_by_id.items():
        fields_per_instrument.setdefault(fobj.instrument_id, []).append(fid)

    def _row_key_for_entity(entity) -> tuple:
        if per_individual:
            return ("ind", entity.id)
        if per_tag_combo:
            return ("tag",) + _entity_tag_combo(
                axis, entity, selected_tag_slots
            )
        return ("sum",)

    accs: dict[tuple, _Acc] = {}
    entity_for_key: dict[tuple, object] = {}
    entity_by_id = {e.id: e for e in entities}
    for entity in entities:
        key = _row_key_for_entity(entity)
        accs.setdefault(key, _Acc())
        entity_for_key.setdefault(key, entity)

    # Assigned counts — one slot per (entity, scope field).
    # Reviewer-side dedupe collapses group fan-out.
    seen_reviewer_assigned: set[tuple[int, int, tuple[str, ...], int]] = set()
    for a in assignments:
        owner_id = (
            a.reviewer_id if axis == "reviewer" else a.reviewee_id
        )
        owner = entity_by_id.get(owner_id)
        if owner is None:
            continue
        key = _row_key_for_entity(owner)
        group_key = group_key_by_assignment.get(a.id)
        for fid in fields_per_instrument.get(a.instrument_id, ()):
            if axis == "reviewer" and group_key is not None:
                dedupe = (a.reviewer_id, a.instrument_id, group_key, fid)
                if dedupe in seen_reviewer_assigned:
                    continue
                seen_reviewer_assigned.add(dedupe)
            accs[key].assigned += 1

    # Response rollup.
    seen_reviewer_response: set[tuple[int, tuple[str, ...], int]] = set()
    if scope.instrument_ids:
        for a_id, owner_id, fid, value in db.execute(
            select(
                Assignment.id,
                Assignment.reviewer_id
                if axis == "reviewer"
                else Assignment.reviewee_id,
                Response.response_field_id,
                Response.value,
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(
                Assignment.session_id == review_session.id,
                Assignment.include.is_(True),
                Assignment.instrument_id.in_(scope.instrument_ids),
            )
        ):
            owner = entity_by_id.get(owner_id)
            if owner is None or not value:
                continue
            if fid not in scope.field_ids:
                continue
            key = _row_key_for_entity(owner)
            group_key = group_key_by_assignment.get(a_id)
            if axis == "reviewer" and group_key is not None:
                dedupe = (owner_id, group_key, fid)
                if dedupe in seen_reviewer_response:
                    continue
                seen_reviewer_response.add(dedupe)
            _ingest(accs[key], scope.field_by_id.get(fid), value)

    rows: list[tuple[str, ...]] = [
        _compose_header(
            review_session, axis, slots, scope.anchor_field
        )
    ]
    if per_individual:
        # One row per individual — even if no responses /
        # assignments accrued to them, the row ships with
        # zero aggregates (matches the metadata cards'
        # ``All reviewers`` ON behaviour).
        for entity in entities:
            key = _row_key_for_entity(entity)
            acc = accs.get(key, _Acc())
            id_cells = _entity_tuple_individual(axis, entity, slots)
            agg_cells = _aggregate_cells(
                axis, slots, acc, scope.anchor_field
            )
            rows.append(id_cells + tuple(agg_cells))
    elif per_tag_combo:
        # One row per distinct tag-combo. Use the first
        # entity carrying that combo as the source for the
        # identification cells.
        seen_combos: set[tuple] = set()
        for entity in entities:
            key = _row_key_for_entity(entity)
            if key in seen_combos:
                continue
            seen_combos.add(key)
            acc = accs[key]
            tag_cells: list[str] = []
            for slot in slots:
                if slot.startswith(f"{axis}:tag-"):
                    n = slot.rsplit("-", 1)[-1]
                    tag_cells.append(
                        getattr(entity, f"tag_{n}", None) or ""
                    )
            agg_cells = _aggregate_cells(
                axis, slots, acc, scope.anchor_field
            )
            rows.append(tuple(tag_cells) + tuple(agg_cells))
    else:
        # Single summary row aggregating across the whole
        # roster.
        summary_acc = _Acc()
        for acc in accs.values():
            summary_acc.assigned += acc.assigned
            summary_acc.numeric_values.extend(acc.numeric_values)
            summary_acc.string_chars += acc.string_chars
            summary_acc.string_count += acc.string_count
            summary_acc.other_count += acc.other_count
            for k, v in acc.fanout_counts.items():
                summary_acc.fanout_counts[k] = (
                    summary_acc.fanout_counts.get(k, 0) + v
                )
        agg_cells = _aggregate_cells(
            axis, slots, summary_acc, scope.anchor_field
        )
        rows.append(tuple(agg_cells))
    return rows
