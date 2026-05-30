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


__all__ = ["build_shape_rows", "compose_shape_header"]


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

    def is_empty(self) -> bool:
        """``True`` when no assignments, no responses, and no
        fan-out counts accrued to this row. Drives the
        ``include_empty_rows=False`` drop predicate per PR 6 of
        the chip-controlled-drop slice."""
        return (
            self.assigned == 0
            and self.count == 0
            and not self.fanout_counts
        )


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


def compose_shape_header(
    db: Session, review_session: ReviewSession, shape: DataShape
) -> tuple[str, ...]:
    """Return just the CSV header row for ``shape``.

    Used by the Extract data page route to embed canonical
    column headers into the server-rendered saved-sub-card
    preview rows — so the preview ``<th>`` cells read the
    same way as the eventual download (``ReviewerName``,
    actual step values, etc.) rather than the raw chip slot
    strings.
    """
    slots: list[str] = json.loads(shape.column_chip_slots)
    scope = _resolve_scope(db, review_session, shape)
    return _compose_header(
        review_session,
        shape.axis,
        slots,
        scope.anchor_field,
        self_review_handling=shape.self_review_handling,
    )


_IDENTITY_SLOT_SUFFIXES = ("name", "email")


def _slot_is_identity(axis: str, slot: str) -> bool:
    """Identity slots describe the row (name / email / tag-N)
    and carry no Self-review handling suffix. Aggregate slots
    (assigned / count / mean / median / min / max / length /
    list-items / discrete-steps) describe the response pool and
    take the suffix."""
    if slot.startswith(f"{axis}:tag-"):
        return True
    for suffix in _IDENTITY_SLOT_SUFFIXES:
        if slot == f"{axis}:{suffix}":
            return True
    return False


def _data_shape_state_suffix(state: str) -> str:
    """Per-state column-name suffix for the Data shape extract.
    Mirrors the metadata-card suffix policy
    (``self_review_handling_filename_suffix`` in
    ``entity_metadata_extract.py``) but only used inside the
    Data shape file-gen — ``both`` is handled by emitting the
    two single-state headers + columns side by side."""
    if state == "exclude_self":
        return "_noself"
    # ``include_self`` and any future single-state default.
    return "_self"


def _compose_identity_header(
    review_session: ReviewSession,
    axis: str,
    slots: list[str],
) -> list[str]:
    """Identity cells (name / email / tag-N) of the header in
    slot order. Carries no Self-review handling suffix."""
    axis_title = "Reviewer" if axis == "reviewer" else "Reviewee"
    header: list[str] = []
    for slot in slots:
        if slot == f"{axis}:name":
            header.append(f"{axis_title}Name")
        elif slot == f"{axis}:email":
            header.append(f"{axis_title}Email")
        elif slot.startswith(f"{axis}:tag-"):
            header.append(
                _tag_header_label(
                    review_session, axis, slot.split(":", 1)[1]
                )
            )
    return header


def _compose_aggregate_header(
    axis: str,
    slots: list[str],
    anchor_field: InstrumentResponseField | None,
    suffix: str,
) -> list[str]:
    """Aggregate cells of the header in slot order, suffixed
    with ``suffix`` (``_self`` / ``_noself``). Fan-out slots
    (``list-items`` / ``discrete-steps``) expand to one suffixed
    column per option / step value."""
    header: list[str] = []
    for slot in slots:
        if _slot_is_identity(axis, slot):
            continue
        if slot == f"{axis}:assigned":
            header.append(f"Assigned{suffix}")
        elif slot == f"{axis}:count":
            header.append(f"Count{suffix}")
        elif slot == f"{axis}:mean":
            header.append(f"Mean{suffix}")
        elif slot == f"{axis}:median":
            header.append(f"Median{suffix}")
        elif slot == f"{axis}:min":
            header.append(f"Min{suffix}")
        elif slot == f"{axis}:max":
            header.append(f"Max{suffix}")
        elif slot == f"{axis}:length":
            header.append(f"Length{suffix}")
        elif slot == f"{axis}:list-items":
            options = (
                _list_option_values(anchor_field)
                if anchor_field
                else []
            )
            header.extend(f"{opt}{suffix}" for opt in options)
        elif slot == f"{axis}:discrete-steps":
            steps = (
                _discrete_step_values(anchor_field)
                if anchor_field
                else []
            )
            header.extend(f"{step}{suffix}" for step in steps)
    return header


def _compose_header(
    review_session: ReviewSession,
    axis: str,
    slots: list[str],
    anchor_field: InstrumentResponseField | None,
    self_review_handling: str = "include_self",
) -> tuple[str, ...]:
    """One header cell per identification slot + per aggregate
    slot. Fan-out slots expand to one cell per option / step
    value.

    Identity cells stay un-suffixed; aggregate cells take a
    ``_self`` / ``_noself`` suffix per the Self-review handling
    chip state. ``both`` duplicates the aggregate block — first
    ``_self``, then ``_noself`` — alongside a single identity
    block.
    """
    identity = _compose_identity_header(review_session, axis, slots)
    if self_review_handling == "both":
        aggregates = (
            _compose_aggregate_header(
                axis, slots, anchor_field, "_self"
            )
            + _compose_aggregate_header(
                axis, slots, anchor_field, "_noself"
            )
        )
    else:
        aggregates = _compose_aggregate_header(
            axis,
            slots,
            anchor_field,
            _data_shape_state_suffix(self_review_handling),
        )
    return tuple(identity + aggregates)


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
    entity_by_id = {e.id: e for e in entities}
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

    # Self-review handling chip — PR B of the chip slice per
    # ``guide/extract_data.md`` § *Self-review handling*. Each
    # state is one pass through the assignment + response pool
    # with an optional ``WHERE NOT is_self_review`` filter; the
    # ``both`` state runs both passes and emits the aggregate-
    # column blocks side by side (Q1 / Q2 resolutions).
    state = shape.self_review_handling
    states_to_run: tuple[str, ...] = (
        ("include_self", "exclude_self")
        if state == "both"
        else (state,)
    )

    per_state_accs: dict[str, dict[tuple, _Acc]] = {}
    for run_state in states_to_run:
        per_state_accs[run_state] = _build_state_accumulators(
            db,
            review_session,
            axis=axis,
            scope=scope,
            entity_by_id=entity_by_id,
            fields_per_instrument=fields_per_instrument,
            row_key_for_entity=_row_key_for_entity,
            exclude_self=(run_state == "exclude_self"),
        )

    rows: list[tuple[str, ...]] = [
        _compose_header(
            review_session,
            axis,
            slots,
            scope.anchor_field,
            self_review_handling=state,
        )
    ]

    def _aggregate_block(row_key: tuple, fallback: _Acc | None = None) -> tuple[str, ...]:
        """Per-row aggregate cells across every state in
        ``states_to_run`` — single block for one-state shapes,
        two blocks (``_self`` then ``_noself`` columns) for
        ``both``."""
        cells: list[str] = []
        for run_state in states_to_run:
            acc = per_state_accs[run_state].get(row_key)
            if acc is None:
                acc = fallback if fallback is not None else _Acc()
            cells.extend(
                _aggregate_cells(axis, slots, acc, scope.anchor_field)
            )
        return tuple(cells)

    # Empty-row drop chip — PR 6 of the chip-controlled-drop
    # slice per the self-review consolidation addendum. When
    # ``include_empty_rows`` is False, drop rows whose every
    # state's accumulator is empty. For one-state shapes that
    # collapses to "drop on empty accumulator"; for ``both``
    # mode, drops only when BOTH ``_self`` and ``_noself``
    # halves are empty (operator opted into both views, so a
    # non-empty half keeps the row visible). Single-summary is
    # always emitted regardless — there's exactly one row, and
    # an empty CSV would be confusing surface.
    drop_empty = not shape.include_empty_rows

    def _row_is_empty(row_key: tuple) -> bool:
        for run_state in states_to_run:
            acc = per_state_accs[run_state].get(row_key)
            if acc is not None and not acc.is_empty():
                return False
        return True

    if per_individual:
        # One row per individual — when ``include_empty_rows`` is
        # True (default), every roster member ships even if no
        # responses / assignments accrued to them; when False, the
        # ``_row_is_empty`` predicate drops the empty ones.
        for entity in entities:
            key = _row_key_for_entity(entity)
            if drop_empty and _row_is_empty(key):
                continue
            id_cells = _entity_tuple_individual(axis, entity, slots)
            rows.append(id_cells + _aggregate_block(key))
    elif per_tag_combo:
        # One row per distinct tag-combo. Use the first entity
        # carrying that combo as the source for the
        # identification cells.
        seen_combos: set[tuple] = set()
        for entity in entities:
            key = _row_key_for_entity(entity)
            if key in seen_combos:
                continue
            seen_combos.add(key)
            if drop_empty and _row_is_empty(key):
                continue
            tag_cells: list[str] = []
            for slot in slots:
                if slot.startswith(f"{axis}:tag-"):
                    n = slot.rsplit("-", 1)[-1]
                    tag_cells.append(
                        getattr(entity, f"tag_{n}", None) or ""
                    )
            rows.append(tuple(tag_cells) + _aggregate_block(key))
    else:
        # Single summary row aggregating across the whole
        # roster. The ``(sum,)`` key is shared across all
        # entities; the per-state accumulators already merged
        # there.
        summary_key = ("sum",)
        rows.append(_aggregate_block(summary_key))
    return rows


def _build_state_accumulators(
    db: Session,
    review_session: ReviewSession,
    *,
    axis: str,
    scope: "_Scope",
    entity_by_id: dict[int, object],
    fields_per_instrument: dict[int, list[int]],
    row_key_for_entity,
    exclude_self: bool,
) -> dict[tuple, _Acc]:
    """One Self-review handling state's accumulators for the Data
    shape pipeline. ``exclude_self=True`` adds
    ``Assignment.is_self_review.is_(False)`` to both the
    assignment-pool and response queries; the rest of the dedupe
    + ingest machinery matches the pre-PR-B single-state flow."""
    assignment_filter = [
        Assignment.session_id == review_session.id,
        Assignment.include.is_(True),
        Assignment.instrument_id.in_(scope.instrument_ids)
        if scope.instrument_ids
        else Assignment.instrument_id.is_(None),
    ]
    if exclude_self:
        assignment_filter.append(Assignment.is_self_review.is_(False))
    assignments = (
        list(db.execute(select(Assignment).where(*assignment_filter)).scalars())
        if scope.instrument_ids
        else []
    )
    group_key_by_assignment = (
        responses_service.group_keys(
            db, assignments=assignments, session_id=review_session.id
        )
        if assignments
        else {}
    )

    accs: dict[tuple, _Acc] = {}
    # Pre-seed every row-key the entity universe could compose,
    # so per-individual rows still ship with zero aggregates
    # when nothing accrues to them.
    for entity in entity_by_id.values():
        accs.setdefault(row_key_for_entity(entity), _Acc())

    # Assigned counts.
    seen_reviewer_assigned: set[
        tuple[int, int, tuple[str, ...], int]
    ] = set()
    for a in assignments:
        owner_id = (
            a.reviewer_id if axis == "reviewer" else a.reviewee_id
        )
        owner = entity_by_id.get(owner_id)
        if owner is None:
            continue
        key = row_key_for_entity(owner)
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
        response_filter = [
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Assignment.instrument_id.in_(scope.instrument_ids),
        ]
        if exclude_self:
            response_filter.append(Assignment.is_self_review.is_(False))
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
            .where(*response_filter)
        ):
            owner = entity_by_id.get(owner_id)
            if owner is None or not value:
                continue
            if fid not in scope.field_ids:
                continue
            key = row_key_for_entity(owner)
            group_key = group_key_by_assignment.get(a_id)
            if axis == "reviewer" and group_key is not None:
                dedupe = (owner_id, group_key, fid)
                if dedupe in seen_reviewer_response:
                    continue
                seen_reviewer_response.add(dedupe)
            _ingest(accs[key], scope.field_by_id.get(fid), value)

    # Roll per-entity accumulators up into the ``(sum,)`` key
    # when the shape composes a single summary row (no identity
    # or tag chips).
    if ("sum",) in accs and len(accs) > 1:
        summary = _Acc()
        for key, acc in accs.items():
            if key == ("sum",):
                continue
            summary.assigned += acc.assigned
            summary.numeric_values.extend(acc.numeric_values)
            summary.string_chars += acc.string_chars
            summary.string_count += acc.string_count
            summary.other_count += acc.other_count
            for k, v in acc.fanout_counts.items():
                summary.fanout_counts[k] = (
                    summary.fanout_counts.get(k, 0) + v
                )
        # Fold whatever already accumulated into the summary key
        # (under ``(sum,)`` the entity loop already wrote there).
        existing = accs[("sum",)]
        summary.assigned += existing.assigned
        summary.numeric_values.extend(existing.numeric_values)
        summary.string_chars += existing.string_chars
        summary.string_count += existing.string_count
        summary.other_count += existing.other_count
        for k, v in existing.fanout_counts.items():
            summary.fanout_counts[k] = (
                summary.fanout_counts.get(k, 0) + v
            )
        accs[("sum",)] = summary
    return accs
