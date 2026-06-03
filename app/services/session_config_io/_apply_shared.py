"""Cross-slice plumbing for the Settings-CSV import package.

Bottom-of-stack: defines the parsed-plan dataclasses, the
``_ParseError`` exception, the section regex patterns +
allowlist constants, and the cell parsers. Every other slice
in this package reads from here; nothing here reads from them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as _dataclass_field
from datetime import datetime
from typing import Any

from app.services.instruments import (
    GROUP_KIND_SENTINEL,
    decode_group_kind,
    encode_group_kind,
)


class _ParseError(Exception):
    """Raised by row routers / cell parsers when a row is malformed."""


@dataclass
class _DisplayFieldSpec:
    source_type: str | None = None
    source_field: str | None = None
    label: str | None = None
    visible: bool = True


@dataclass
class _ResponseFieldSpec:
    field_key: str | None = None
    label: str | None = None
    response_type: str | None = None
    required: bool = False
    help_text: str | None = None
    help_text_visible: bool = True
    # Segment 18N PR 5 — inline type + bounds + per-field visibility.
    # Pre-PR-5 the round-trip lost every semantic bound (the
    # serializer exported only the legacy ``response_type`` label
    # after 18J Wave 2 PR iii-b4 retired the RTD table).
    data_type: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    list_csv: str | None = None
    visible: bool = True


@dataclass
class _InstrumentSpec:
    name: str | None = None
    short_label: str | None = None
    description: str | None = None
    order: int | None = None
    accepting_responses: bool = False
    responses_visible_when_closed: bool = False
    sort_display_fields: list[Any] | None = None
    group_kind: str | None = None
    rule_set_name: str | None = None
    # Segment 18N PR 5 — three operator-input fields the pre-PR-5
    # round-trip silently dropped: drag-gripper column widths, the
    # 18M page-break flag, and the Band 2 chip selections + sample-
    # reviewee pick JSON blob.
    column_widths: dict[str, Any] | None = None
    starts_new_page: bool = False
    band2_state: dict[str, Any] | None = None
    display_fields: dict[int, _DisplayFieldSpec] = _dataclass_field(default_factory=dict)
    response_fields: dict[int, _ResponseFieldSpec] = _dataclass_field(default_factory=dict)


@dataclass
class _RuleSetSpec:
    name: str | None = None
    description: str | None = None
    combinator: str | None = None
    exclude_self_reviews: bool = False
    seed: int | None = None
    rules_json: list[Any] = _dataclass_field(default_factory=list)


@dataclass
class _FieldLabelSpec:
    source_type: str
    source_field: str
    label: str


@dataclass
class _DataShapeSpec:
    """One ``data_shapes[N].*`` row group accumulated during
    parse. Resolves the portable ``instrument_short_label`` /
    ``response_field_key`` references at apply time against
    the imported session's instruments."""

    name: str | None = None
    axis: str | None = None
    instrument_short_label: str | None = None
    response_field_key: str | None = None
    column_chip_slots: list[str] = _dataclass_field(default_factory=list)
    # PR B of the Self-review handling chip slice. Default to
    # ``include_self`` so a pre-PR-B Settings CSV (which doesn't
    # carry the row) imports cleanly with today's behaviour.
    self_review_handling: str = "include_self"
    # PR 6 of the chip-controlled-drop slice. Default ``True`` so
    # a pre-PR-6 Settings CSV (which doesn't carry the row)
    # imports cleanly with today's behaviour.
    include_empty_rows: bool = True


@dataclass
class _ParsedConfig:
    session_overrides: dict[str, Any] = _dataclass_field(default_factory=dict)
    email_overrides: dict[str, Any] = _dataclass_field(default_factory=dict)
    instruments: dict[int, _InstrumentSpec] = _dataclass_field(default_factory=dict)
    session_rule_sets: dict[int, _RuleSetSpec] = _dataclass_field(default_factory=dict)
    field_labels: list[_FieldLabelSpec] = _dataclass_field(default_factory=list)
    data_shapes: dict[int, _DataShapeSpec] = _dataclass_field(default_factory=dict)


_VALID_DATA_TYPES = {
    "string",
    "integer",
    "decimal",
    "boolean",
    "datetime",
    "enum",
    "csv_list",
    "json",
}
_VALID_COMBINATORS = frozenset({"ALL_OF", "ANY_OF", "PIPELINE"})
_VALID_DF_SOURCE_TYPES = frozenset({"reviewee", "pair_context"})
_VALID_FL_SOURCE_TYPES = frozenset({"reviewer", "reviewee", "pair_context"})

# Per-source allowlist for ``field_labels.*`` rows, mirroring
# ``app.services.field_labels._VALID_SOURCE_FIELDS``. The DB column
# is permissive (VARCHAR(64) with no enum gate); this map is the
# only validation layer that keeps the table aligned with the
# friendly-label intent on import. Reviewee identity fields
# (Name / Email_Identifier / Profile) dropped 2026-05-31 alongside
# the editor retirement (``guide/archive/participant_model_upgrade.md``
# §3.7); Settings-CSV imports for those slots are now rejected.
_VALID_FL_SOURCE_FIELDS: dict[str, frozenset[str]] = {
    "reviewer": frozenset({"tag_1", "tag_2", "tag_3"}),
    "reviewee": frozenset({"tag_1", "tag_2", "tag_3"}),
    "pair_context": frozenset({"1", "2", "3"}),
}

# Bracketed-key parsers. Each pattern captures the index / name and
# an optional sub-key tail; the apply step routes by tail.
_RX_INSTRUMENT_DF = re.compile(
    r"^instruments\[(\d+)\]\.display_fields\[(\d+)\]\.(\w+)$"
)
_RX_INSTRUMENT_RF = re.compile(
    r"^instruments\[(\d+)\]\.response_fields\[(\d+)\]\.(\w+)$"
)
_RX_INSTRUMENT = re.compile(r"^instruments\[(\d+)\]\.(\w+)$")
_RX_RULE_SET = re.compile(r"^session_rule_sets\[(\d+)\]\.(\w+)$")
_RX_EMAIL = re.compile(r"^email_overrides\.(\w+)\.(\w+)$")
_RX_FIELD_LABEL = re.compile(r"^field_labels\.(\w+)\.([^.]+)$")
_RX_DATA_SHAPE = re.compile(r"^data_shapes\[(\d+)\]\.(\w+)$")


# --------------------------------------------------------------------------- #
# Cell parsers
# --------------------------------------------------------------------------- #


def _parse_bool(value: str, *, default: bool = False) -> bool:
    if not value:
        return default
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    raise _ParseError(f"expected boolean, got {value!r}")


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise _ParseError(f"expected integer, got {value!r}") from exc


def _parse_decimal(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise _ParseError(f"expected decimal, got {value!r}") from exc


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise _ParseError(
            f"expected ISO-8601 datetime, got {value!r}"
        ) from exc


def _parse_json(value: str, *, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise _ParseError(f"expected JSON, got {value!r}") from exc


def _parse_group_kind(value: str) -> str | None:
    """Parse an ``instruments[].group_kind`` config value.

    Empty/NULL = a per-reviewee instrument. A non-empty value is the
    group-scoped instrument's boundary spec, in the same encoding the
    ``Instrument.group_kind`` column uses (the value the serialiser
    emits): either the no-boundary sentinel (``GROUP_KIND_SENTINEL``,
    a group instrument with no boundary tag — one universe-wide
    group), or a comma-joined list of distinct boundary codes —
    ``r1`` / ``r2`` / ``r3`` for reviewee tags, ``p1`` / ``p2`` /
    ``p3`` for pair-context tags. Returns the canonical column value.
    """
    if not value:
        return None
    value = value.strip()
    if value == GROUP_KIND_SENTINEL:
        return GROUP_KIND_SENTINEL
    codes = [part.strip() for part in value.split(",")]
    invalid = [c for c in codes if not decode_group_kind(c)]
    if invalid or len(set(codes)) != len(codes):
        raise _ParseError(
            f"invalid instrument group_kind {value!r}; expected "
            f"{GROUP_KIND_SENTINEL!r} or a comma-joined list of "
            f"distinct boundary codes (r1/r2/r3 for reviewee tags, "
            f"p1/p2/p3 for pair-context tags)"
        )
    return encode_group_kind(decode_group_kind(value))
