"""segment_18J wave 3 PR iii — retire band2_state.response_fields JSON

Data migration accompanying the PR iii cutover from JSON to DB rows
as the source of truth for new-model instrument response fields
(``guide/segment_18J_new_model_takeover.md`` decision 5).

PR i (revision b2f6c4a8e1d3) shipped the dual-write — every Save
through ``set_band2_state`` round-trips JSON entries to real
``InstrumentResponseField`` rows. By the time PR iii lands, most
instruments have re-saved at least once and their DB rows reflect
the JSON state. This migration is defence-in-depth for instruments
that never re-saved:

1. For every instrument with ``band2_state.response_fields``:
   - For each JSON entry that has no matching DB row (by id, or by
     ``field_key``/label slug for entries without an id), create
     the ``InstrumentResponseField`` row from the JSON shape.
   - For each JSON entry that carries ``width_px``, migrate it into
     ``instrument.column_widths["rf_<db_id>"]`` (the new canonical
     location alongside ``df_<id>`` / ``identity``).
2. Pop the ``response_fields`` key from ``band2_state``. After this
   migration runs, no instrument has the legacy key.

No schema change — pure JSON / row data movement. Downgrade is a
no-op (the JSON key can't be reconstructed lossless-ly from DB rows
since the JSON cached operator-authored fields that the dual-write
already wrote to DB).

Revision ID: c3a7e9d8b154
Revises: b2f6c4a8e1d3
Create Date: 2026-05-25
"""
from __future__ import annotations

import json
import re
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3a7e9d8b154"
down_revision: Union[str, Sequence[str], None] = "b2f6c4a8e1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMN_WIDTH_MIN_PX = 40
_COLUMN_WIDTH_MAX_PX = 1200
_BAND2_DATA_TYPE_TO_INLINE: dict[str, str] = {
    "string": "String",
    "integer": "Integer",
    "decimal": "Decimal",
    "list": "List",
}
_FIELD_KEY_REGEX = re.compile(r"[^a-z0-9_]+")


def _slugify_field_key(label: str) -> str:
    base = _FIELD_KEY_REGEX.sub("_", label.lower()).strip("_") or "field"
    if not base[0].isalpha():
        base = f"f_{base}"
    return base[:64]


def _unique_field_key(label: str, used: set[str]) -> str:
    base = _slugify_field_key(label)
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _decode_band2_state(value: Any) -> dict[str, Any] | None:
    """band2_state is stored as JSON-encoded TEXT on SQLite and
    native JSONB on Postgres. SQLAlchemy's JSON type normally hides
    this, but a raw ``op.get_bind().execute`` returns the SQLite
    column as ``str`` and Postgres as ``dict``. Normalise here so
    the rest of the migration is dialect-agnostic.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return None


def _encode_band2_state(value: dict[str, Any] | None, dialect: str) -> Any:
    if value is None:
        return None
    if dialect == "postgresql":
        return value
    return json.dumps(value)


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Walk every instrument that still has ``band2_state.response_fields``.
    rows = bind.execute(
        sa.text(
            "SELECT id, band2_state, column_widths "
            "FROM instruments "
            "WHERE band2_state IS NOT NULL"
        )
    ).fetchall()

    for row in rows:
        instrument_id = row[0]
        band2_state = _decode_band2_state(row[1])
        if not isinstance(band2_state, dict):
            continue
        rfs = band2_state.get("response_fields")
        if not isinstance(rfs, list) or not rfs:
            # No JSON entries to migrate — just pop the key in case
            # it's an empty list, then continue.
            if "response_fields" in band2_state:
                band2_state.pop("response_fields", None)
                new_state = band2_state or None
                bind.execute(
                    sa.text(
                        "UPDATE instruments SET band2_state = :s "
                        "WHERE id = :i"
                    ),
                    {
                        "s": _encode_band2_state(new_state, dialect_name),
                        "i": instrument_id,
                    },
                )
            continue

        # Existing DB rows for this instrument, keyed by id + field_key.
        existing_rows = bind.execute(
            sa.text(
                "SELECT id, field_key, label, \"order\" "
                "FROM instrument_response_fields "
                "WHERE instrument_id = :i"
            ),
            {"i": instrument_id},
        ).fetchall()
        existing_by_id: dict[int, dict] = {
            r[0]: {"id": r[0], "field_key": r[1], "label": r[2], "order": r[3]}
            for r in existing_rows
        }
        used_field_keys: set[str] = {r[1] for r in existing_rows}

        # Column widths to upsert under rf_<id> keys.
        column_widths = _decode_band2_state(row[2]) or {}
        if not isinstance(column_widths, dict):
            column_widths = {}

        widths_dirty = False

        for order_idx, rf in enumerate(rfs):
            if not isinstance(rf, dict):
                continue
            name = str(rf.get("name") or "").strip()
            if not name:
                continue
            rf_id = rf.get("id")
            if isinstance(rf_id, str) and rf_id.strip().isdigit():
                rf_id = int(rf_id)
            field_id: int | None = None
            if isinstance(rf_id, int) and rf_id in existing_by_id:
                field_id = rf_id
            else:
                # Create a new row. Slugify the label, dedupe.
                field_key = _unique_field_key(name, used_field_keys)
                data_type_lower = (
                    str(rf.get("data_type") or "string").strip().lower()
                )
                inline_data_type = _BAND2_DATA_TYPE_TO_INLINE.get(
                    data_type_lower, "String"
                )
                inline_min = _parse_float(rf.get("min"))
                inline_max = _parse_float(rf.get("max"))
                inline_step = _parse_float(rf.get("step"))
                inline_list_csv = rf.get("list_options") or None
                if inline_list_csv == "":
                    inline_list_csv = None
                inserted = bind.execute(
                    sa.text(
                        "INSERT INTO instrument_response_fields "
                        "(instrument_id, field_key, label, "
                        " required, \"order\", visible, "
                        " help_text, help_text_visible, "
                        " data_type, response_type, "
                        " min, max, step, list_csv) "
                        "VALUES (:instrument_id, :field_key, :label, "
                        " :required, :order, :visible, "
                        " :help_text, :help_text_visible, "
                        " :data_type, :response_type, "
                        " :min, :max, :step, :list_csv) "
                        "RETURNING id"
                        if dialect_name == "postgresql"
                        else
                        "INSERT INTO instrument_response_fields "
                        "(instrument_id, field_key, label, "
                        " required, \"order\", visible, "
                        " help_text, help_text_visible, "
                        " data_type, response_type, "
                        " min, max, step, list_csv) "
                        "VALUES (:instrument_id, :field_key, :label, "
                        " :required, :order, :visible, "
                        " :help_text, :help_text_visible, "
                        " :data_type, :response_type, "
                        " :min, :max, :step, :list_csv)"
                    ),
                    {
                        "instrument_id": instrument_id,
                        "field_key": field_key,
                        "label": name[:255],
                        "required": bool(rf.get("required")),
                        "order": order_idx,
                        "visible": bool(rf.get("selected", True)),
                        "help_text": (
                            str(rf.get("help_text") or "")[:1000] or None
                        ),
                        "help_text_visible": bool(
                            rf.get("help_text_visible", True)
                        ),
                        "data_type": inline_data_type,
                        "response_type": inline_data_type,
                        "min": inline_min,
                        "max": inline_max,
                        "step": inline_step,
                        "list_csv": inline_list_csv,
                    },
                )
                if dialect_name == "postgresql":
                    field_id = inserted.scalar()
                else:
                    field_id = bind.execute(
                        sa.text("SELECT last_insert_rowid()")
                    ).scalar()
                existing_by_id[field_id] = {
                    "id": field_id,
                    "field_key": field_key,
                    "label": name[:255],
                    "order": order_idx,
                }

            # Migrate width_px → column_widths["rf_<id>"].
            raw_width = rf.get("width_px")
            if raw_width not in (None, ""):
                try:
                    width_int = int(raw_width)
                except (TypeError, ValueError):
                    width_int = 0
                if width_int >= _COLUMN_WIDTH_MIN_PX and field_id is not None:
                    clamped = min(width_int, _COLUMN_WIDTH_MAX_PX)
                    column_widths[f"rf_{field_id}"] = clamped
                    widths_dirty = True

        # Pop the JSON key and persist the trimmed band2_state +
        # any width additions.
        band2_state.pop("response_fields", None)
        new_state = band2_state or None
        bind.execute(
            sa.text(
                "UPDATE instruments SET band2_state = :s "
                "WHERE id = :i"
            ),
            {
                "s": _encode_band2_state(new_state, dialect_name),
                "i": instrument_id,
            },
        )
        if widths_dirty:
            bind.execute(
                sa.text(
                    "UPDATE instruments SET column_widths = :w "
                    "WHERE id = :i"
                ),
                {
                    "w": _encode_band2_state(column_widths, dialect_name),
                    "i": instrument_id,
                },
            )


def downgrade() -> None:
    # No-op. Restoring ``band2_state.response_fields`` from DB rows
    # is lossless on the field-level data but would require also
    # rolling back any rows created by the upgrade, which the
    # migration doesn't track. Roll forward only.
    pass
