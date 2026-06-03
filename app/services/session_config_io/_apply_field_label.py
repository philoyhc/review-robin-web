"""``field_labels.<source_type>.<source_field>`` parse + apply."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionFieldLabel

from ._apply_shared import (
    _RX_FIELD_LABEL,
    _VALID_FL_SOURCE_FIELDS,
    _VALID_FL_SOURCE_TYPES,
    _FieldLabelSpec,
    _ParsedConfig,
    _ParseError,
)


def _apply_field_label_kv(
    plan: _ParsedConfig, field_path: str, value: str
) -> None:
    match = _RX_FIELD_LABEL.match(field_path)
    if match is None:
        raise _ParseError(
            f"unrecognised field_labels.* key {field_path!r}"
        )
    source_type, source_field = match.group(1), match.group(2)
    if source_type not in _VALID_FL_SOURCE_TYPES:
        raise _ParseError(
            f"unknown field_labels source_type {source_type!r}; "
            f"expected one of {sorted(_VALID_FL_SOURCE_TYPES)}"
        )
    allowed_fields = _VALID_FL_SOURCE_FIELDS[source_type]
    if source_field not in allowed_fields:
        raise _ParseError(
            f"unknown field_labels source_field {source_field!r} "
            f"for source_type {source_type!r}; expected one of "
            f"{sorted(allowed_fields)}"
        )
    if value:
        plan.field_labels.append(
            _FieldLabelSpec(
                source_type=source_type,
                source_field=source_field,
                label=value,
            )
        )


def _apply_field_labels(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Upsert by ``(source_type, source_field)``; delete existing
    rows not in the CSV. Inert pre-15A but the wipe-and-replace
    contract still applies."""

    existing = {
        (lbl.source_type, lbl.source_field): lbl
        for lbl in db.execute(
            select(SessionFieldLabel).where(
                SessionFieldLabel.session_id == review_session.id
            )
        ).scalars()
    }

    written = 0
    for spec in plan.field_labels:
        key = (spec.source_type, spec.source_field)
        lbl = existing.pop(key, None)
        if lbl is None:
            db.add(
                SessionFieldLabel(
                    session_id=review_session.id,
                    source_type=spec.source_type,
                    source_field=spec.source_field,
                    label=spec.label,
                )
            )
        else:
            lbl.label = spec.label
        written += 1

    for orphan in existing.values():
        db.delete(orphan)

    return written
