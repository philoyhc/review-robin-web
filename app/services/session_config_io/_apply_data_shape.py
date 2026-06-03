"""``data_shapes[N].*`` parse + apply."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models import ReviewSession

from ._apply_shared import (
    _RX_DATA_SHAPE,
    _DataShapeSpec,
    _ParsedConfig,
    _ParseError,
    _parse_bool,
    _parse_json,
)


def _apply_data_shape_kv(
    plan: _ParsedConfig,
    field_path: str,
    value: str,
    data_type: str,
) -> None:
    """Route one ``data_shapes[N].<key>`` row into the
    ``_DataShapeSpec`` for index N. Recognised keys:
    ``name`` / ``axis`` / ``instrument_short_label`` /
    ``response_field_key`` / ``column_chip_slots``. Unknown
    keys raise ``_ParseError`` so a typo'd hand-edit surfaces."""
    match = _RX_DATA_SHAPE.match(field_path)
    if match is None:
        raise _ParseError(
            f"unrecognised data_shapes.* key {field_path!r}"
        )
    idx = int(match.group(1))
    key = match.group(2)
    spec = plan.data_shapes.setdefault(idx, _DataShapeSpec())
    if key == "name":
        spec.name = value or None
    elif key == "axis":
        spec.axis = value or None
    elif key == "instrument_short_label":
        spec.instrument_short_label = value or None
    elif key == "response_field_key":
        spec.response_field_key = value or None
    elif key == "column_chip_slots":
        slots = _parse_json(value, default=[])
        if not isinstance(slots, list):
            raise _ParseError(
                f"data_shapes[{idx}].column_chip_slots must be a "
                f"JSON list, got {type(slots).__name__}"
            )
        spec.column_chip_slots = [str(s) for s in slots]
    elif key == "self_review_handling":
        spec.self_review_handling = value or "include_self"
    elif key == "include_empty_rows":
        spec.include_empty_rows = _parse_bool(value, default=True)
    else:
        raise _ParseError(
            f"unknown data_shapes key {key!r} in {field_path!r}"
        )
    # ``data_type`` is unused in this branch — every
    # ``data_shapes`` row's intended interpretation is fixed
    # by the suffix, not by the column hint.
    _ = data_type


def _apply_data_shapes(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Wipe-and-replace the session's saved Data shapes from
    the CSV plan.

    Resolves portable references
    (``instrument_short_label`` / ``response_field_key``)
    against the imported session's just-applied instruments
    + response fields. Shapes whose references don't resolve
    silently get those fields zeroed (the shape persists with
    a widened scope rather than failing the whole import).

    Returns the number of shapes written.
    """
    from app.db.models import DataShape, InstrumentResponseField

    # Wipe existing shapes — replace semantics align with the
    # rest of the apply step (instruments / RuleSets / field
    # labels). Shapes that CASCADED away when instruments
    # were wiped above are already gone; this pass clears
    # session-scope-only shapes too.
    db.execute(
        DataShape.__table__.delete().where(
            DataShape.session_id == review_session.id
        )
    )

    instr_by_short = {
        (i.short_label or "").strip(): i
        for i in review_session.instruments
        if (i.short_label or "").strip()
    }
    field_lookup: dict[tuple[str, str], InstrumentResponseField] = {}
    for instrument in review_session.instruments:
        short = (instrument.short_label or "").strip()
        if not short:
            continue
        for f in instrument.response_fields:
            field_lookup[(short, f.field_key)] = f

    written = 0
    for spec in plan.data_shapes.values():
        if not spec.name or not spec.axis:
            continue
        if spec.axis not in ("reviewer", "reviewee"):
            continue
        instr = (
            instr_by_short.get(spec.instrument_short_label.strip())
            if spec.instrument_short_label
            else None
        )
        field = (
            field_lookup.get(
                (spec.instrument_short_label.strip(), spec.response_field_key)
            )
            if (
                spec.instrument_short_label
                and spec.response_field_key
            )
            else None
        )
        # ``self_review_handling`` defaults to ``include_self`` on
        # the ``_DataShapeSpec`` dataclass — pre-PR-B Settings
        # CSVs (which don't carry the row) import cleanly with
        # today's behaviour. Unknown strings fall back to the
        # default so a hand-tampered CSV never crashes the import.
        valid_srh = {"include_self", "exclude_self", "both"}
        srh = (
            spec.self_review_handling
            if spec.self_review_handling in valid_srh
            else "include_self"
        )
        db.add(
            DataShape(
                session_id=review_session.id,
                name=spec.name,
                axis=spec.axis,
                instrument_id=instr.id if instr is not None else None,
                response_field_id=field.id if field is not None else None,
                column_chip_slots=json.dumps(spec.column_chip_slots),
                self_review_handling=srh,
                include_empty_rows=spec.include_empty_rows,
            )
        )
        written += 1
    return written
