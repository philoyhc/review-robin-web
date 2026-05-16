"""Settings CSV import — ``apply_session_config``.

Parses a Settings CSV (3-column ``field,value,data_type`` shape)
and applies it to a session as a wipe-and-replace. Two-phase:
parse + validate first (collect every error before reporting),
then apply in a single transaction.

Reachable only via Quick Setup slot 4 (graduated in 12A-3 PR 4) —
no standalone Manage page. The lifecycle gate
(``status in {"draft", "validated"}``) lives at the route layer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as _dataclass_field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    ReviewSession,
    SessionFieldLabel,
    SessionRuleSet,
    User,
)
from app.services import audit
from app.services import session_lifecycle as lifecycle
from app.services.email_templates import (
    OVERRIDE_KEYS,
    RESPONSES_RECEIVED_ENABLED_KEY,
)
from app.services.instruments._rtds import (
    SEEDED_RESPONSE_TYPE_DEFINITIONS,
    validation_block_for_rtd,
)
from app.services.rules.seeds import (
    SEEDED_RULE_SETS as _SEEDED_RULE_SETS,
    materialise_seed_rule_sets,
)

from app.services.session_config_io._rows import Row

# Names of seeded RTDs / RuleSets — both auto-materialise on the
# destination session, so they are valid cross-row reference
# targets even when no CSV row defines them.
_SEEDED_RTD_NAMES: frozenset[str] = frozenset(
    spec["response_type"] for spec in SEEDED_RESPONSE_TYPE_DEFINITIONS
)
_SEEDED_RULE_SET_NAMES: frozenset[str] = frozenset(
    rs.name for rs in _SEEDED_RULE_SETS
)


@dataclass(frozen=True)
class ApplyError:
    """One validation / parse error from
    ``apply_session_config``."""

    row_number: int
    """1-based CSV row number; ``0`` for global / cross-row errors
    (e.g. an unresolved ``rule_set_name`` reference)."""

    field: str
    message: str


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of an ``apply_session_config`` call.

    On success ``counts`` carries the number of rows written per
    section (e.g. ``{"rtds": 3, "instruments": 2, ...}``) and
    ``errors`` is empty. On failure ``errors`` enumerates every
    parse / validation issue and ``counts`` is empty (the apply
    transaction never ran)."""

    counts: dict[str, int]
    errors: list[ApplyError]

    @property
    def ok(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------- #
# Parse phase — typed plan
# --------------------------------------------------------------------------- #


@dataclass
class _RtdSpec:
    response_type: str
    data_type: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    list_csv: str | None = None


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
class _ParsedConfig:
    session_overrides: dict[str, Any] = _dataclass_field(default_factory=dict)
    email_overrides: dict[str, Any] = _dataclass_field(default_factory=dict)
    rtds: dict[str, _RtdSpec] = _dataclass_field(default_factory=dict)
    instruments: dict[int, _InstrumentSpec] = _dataclass_field(default_factory=dict)
    session_rule_sets: dict[int, _RuleSetSpec] = _dataclass_field(default_factory=dict)
    field_labels: list[_FieldLabelSpec] = _dataclass_field(default_factory=list)


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
# Documented import vocabulary (per the 12A-2 plan) plus the
# model's capitalized values that today's export emits directly
# (``ResponseTypeDefinition.data_type`` carries ``Integer`` /
# ``Decimal`` / ``String`` / ``List``). Accepting both shapes
# keeps round-trip byte-stable without flipping the export.
_VALID_RTD_DATA_TYPES = frozenset(
    {
        "int",
        "decimal",
        "short_text",
        "long_text",
        "list",
        "Integer",
        "Decimal",
        "String",
        "List",
    }
)
_VALID_GROUP_KINDS = frozenset({"tag_1", "tag_2", "tag_3"})
_VALID_DF_SOURCE_TYPES = frozenset({"reviewee", "pair_context"})
_VALID_FL_SOURCE_TYPES = frozenset({"reviewer", "reviewee", "pair_context"})

# Per-source allowlist for ``field_labels.*`` rows, mirroring
# ``app.services.field_labels._VALID_SOURCE_FIELDS``. The DB column
# is permissive (VARCHAR(64) with no enum gate); this map is the
# only validation layer that keeps the table aligned with the
# 12-slot intent on import.
_VALID_FL_SOURCE_FIELDS: dict[str, frozenset[str]] = {
    "reviewer": frozenset({"tag_1", "tag_2", "tag_3"}),
    "reviewee": frozenset(
        {
            "name",
            "email_or_identifier",
            "tag_1",
            "tag_2",
            "tag_3",
            "profile_link",
        }
    ),
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
_RX_RTD = re.compile(r"^rtds\[([^\]]+)\]\.(\w+)$")
_RX_RULE_SET = re.compile(r"^session_rule_sets\[(\d+)\]\.(\w+)$")
_RX_EMAIL = re.compile(r"^email_overrides\.(\w+)\.(\w+)$")
_RX_FIELD_LABEL = re.compile(r"^field_labels\.(\w+)\.([^.]+)$")


def apply_session_config(
    db: Session,
    review_session: ReviewSession,
    rows: list[Row],
    *,
    user: User | None = None,
    correlation_id: str | None = None,
) -> ApplyResult:
    """Parse + apply a Settings CSV against ``review_session``.

    Phase 1 — parse + validate every row. Collect every error
    before reporting; one bad row doesn't mask the next.

    Phase 2 — apply the typed plan in a single DB transaction
    (wipe-and-replace per the "Idempotency model" section of the
    12A-2 plan). On any apply error, raise; the caller's
    transaction handler rolls back.

    Returns ``ApplyResult`` with ``counts`` on success, ``errors``
    on validation failure (apply is not attempted)."""

    plan, errors = _parse_rows(rows)
    if errors:
        return ApplyResult(counts={}, errors=errors)

    counts = _apply_plan(
        db,
        review_session,
        plan,
        user=user,
        correlation_id=correlation_id,
    )
    return ApplyResult(counts=counts, errors=[])


def _parse_rows(rows: list[Row]) -> tuple[_ParsedConfig, list[ApplyError]]:
    plan = _ParsedConfig()
    errors: list[ApplyError] = []

    for index, row in enumerate(rows, start=1):
        field_path = (row.field or "").strip()
        if not field_path:
            continue
        data_type = (row.data_type or "").strip().lower()
        if data_type and data_type not in _VALID_DATA_TYPES:
            errors.append(
                ApplyError(
                    row_number=index,
                    field=field_path,
                    message=(
                        f"unknown data_type {row.data_type!r}; expected "
                        f"one of {sorted(_VALID_DATA_TYPES)}"
                    ),
                )
            )
            continue

        try:
            _route_row(plan, index, field_path, row.value, data_type)
        except _ParseError as exc:
            errors.append(
                ApplyError(
                    row_number=index,
                    field=field_path,
                    message=str(exc),
                )
            )

    # Cross-row validations. These run after row parsing so the
    # error list orders parse errors first.
    errors.extend(_cross_row_errors(plan))
    return plan, errors


class _ParseError(Exception):
    """Raised by ``_route_row`` / cell parsers when a row is malformed."""


def _route_row(
    plan: _ParsedConfig,
    index: int,
    field_path: str,
    value: str,
    data_type: str,
) -> None:
    if field_path.startswith("session."):
        _apply_session_kv(plan, field_path, value)
        return
    if field_path.startswith("email_overrides."):
        _apply_email_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("rtds["):
        _apply_rtd_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("instruments["):
        _apply_instrument_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("session_rule_sets["):
        _apply_rule_set_kv(plan, field_path, value, data_type)
        return
    if field_path.startswith("field_labels."):
        _apply_field_label_kv(plan, field_path, value)
        return
    # Unknown field path — silently ignore. Defensive: the export
    # is the canonical key vocabulary; future export-side keys
    # should land before importer-side support, so unknown keys
    # are forward-compatible padding.


def _apply_session_kv(
    plan: _ParsedConfig, field_path: str, value: str
) -> None:
    key = field_path.removeprefix("session.")
    if key in {"assignment_mode", "status"}:
        # Defensively ignored even if exported — these are
        # machine-derived per the inclusion model.
        return
    if key == "deadline":
        plan.session_overrides[key] = _parse_datetime(value)
        return
    if key in {"name", "code", "description", "help_contact"}:
        plan.session_overrides[key] = value or None


def _apply_email_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    match = _RX_EMAIL.match(field_path)
    if match is None:
        raise _ParseError(f"unrecognised email_overrides key {field_path!r}")
    kind, slot = match.group(1), match.group(2)
    if slot == "enabled":
        # ``responses_received.enabled`` boolean; the legacy
        # ``responses_received_enabled`` key in the JSON dict is
        # the canonical home (matches the resolver).
        plan.email_overrides[RESPONSES_RECEIVED_ENABLED_KEY] = _parse_bool(
            value, default=True
        )
        return
    legacy_key = f"{kind}_{slot}"
    if legacy_key not in OVERRIDE_KEYS:
        raise _ParseError(
            f"unknown email override slot {field_path!r}"
        )
    if value:
        plan.email_overrides[legacy_key] = value
    # Empty cell ⇒ key absent ⇒ "use default" (matches resolver).
    del data_type  # unused; cell is always string here


def _apply_rtd_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    match = _RX_RTD.match(field_path)
    if match is None:
        raise _ParseError(f"unrecognised rtds[] key {field_path!r}")
    rtd_name = match.group(1)
    attr = match.group(2)
    spec = plan.rtds.setdefault(rtd_name, _RtdSpec(response_type=rtd_name))
    if attr == "data_type":
        if value and value not in _VALID_RTD_DATA_TYPES:
            raise _ParseError(
                f"unknown RTD data_type {value!r}; expected one of "
                f"{sorted(_VALID_RTD_DATA_TYPES)}"
            )
        spec.data_type = value or None
        return
    if attr in {"min", "max", "step"}:
        setattr(spec, attr, _parse_decimal(value))
        return
    if attr == "list_csv":
        spec.list_csv = value or None
        return
    raise _ParseError(f"unknown rtds[] attribute {attr!r}")
    del data_type  # unused


def _apply_instrument_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    df_match = _RX_INSTRUMENT_DF.match(field_path)
    if df_match is not None:
        n, m, attr = (
            int(df_match.group(1)),
            int(df_match.group(2)),
            df_match.group(3),
        )
        instrument = plan.instruments.setdefault(n, _InstrumentSpec())
        df = instrument.display_fields.setdefault(m, _DisplayFieldSpec())
        if attr == "source_type":
            if value and value not in _VALID_DF_SOURCE_TYPES:
                raise _ParseError(
                    f"unknown display-field source_type {value!r}; "
                    f"expected one of {sorted(_VALID_DF_SOURCE_TYPES)}"
                )
            df.source_type = value or None
        elif attr == "source_field":
            df.source_field = value or None
        elif attr == "label":
            # 15A Slice 1 — display-field per-instrument label
            # retired. Legacy Settings CSVs may still carry this
            # row; tolerate it and silently drop the value so
            # round-trip imports continue to succeed.
            pass
        elif attr == "visible":
            df.visible = _parse_bool(value, default=True)
        else:
            raise _ParseError(
                f"unknown display_fields[] attribute {attr!r}"
            )
        return

    rf_match = _RX_INSTRUMENT_RF.match(field_path)
    if rf_match is not None:
        n, m, attr = (
            int(rf_match.group(1)),
            int(rf_match.group(2)),
            rf_match.group(3),
        )
        instrument = plan.instruments.setdefault(n, _InstrumentSpec())
        rf = instrument.response_fields.setdefault(m, _ResponseFieldSpec())
        if attr == "field_key":
            rf.field_key = value or None
        elif attr == "label":
            rf.label = value or None
        elif attr == "response_type":
            rf.response_type = value or None
        elif attr == "required":
            rf.required = _parse_bool(value)
        elif attr == "help_text":
            rf.help_text = value or None
        elif attr == "help_text_visible":
            rf.help_text_visible = _parse_bool(value, default=True)
        else:
            raise _ParseError(
                f"unknown response_fields[] attribute {attr!r}"
            )
        return

    inst_match = _RX_INSTRUMENT.match(field_path)
    if inst_match is None:
        raise _ParseError(f"unrecognised instruments[] key {field_path!r}")
    n, attr = int(inst_match.group(1)), inst_match.group(2)
    instrument = plan.instruments.setdefault(n, _InstrumentSpec())
    if attr == "name":
        instrument.name = value or None
    elif attr == "short_label":
        instrument.short_label = value or None
    elif attr == "description":
        instrument.description = value or None
    elif attr == "order":
        instrument.order = _parse_int(value)
    elif attr == "accepting_responses":
        instrument.accepting_responses = _parse_bool(value)
    elif attr == "responses_visible_when_closed":
        instrument.responses_visible_when_closed = _parse_bool(value)
    elif attr == "sort_display_fields":
        instrument.sort_display_fields = _parse_json(value, default=[])
    elif attr == "group_kind":
        instrument.group_kind = _parse_group_kind(value)
    elif attr == "rule_set_name":
        instrument.rule_set_name = value or None
    else:
        raise _ParseError(f"unknown instruments[] attribute {attr!r}")
    del data_type  # unused; type-checked by parser per attr


def _apply_rule_set_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    match = _RX_RULE_SET.match(field_path)
    if match is None:
        raise _ParseError(
            f"unrecognised session_rule_sets[] key {field_path!r}"
        )
    n, attr = int(match.group(1)), match.group(2)
    spec = plan.session_rule_sets.setdefault(n, _RuleSetSpec())
    if attr == "name":
        spec.name = value or None
    elif attr == "description":
        spec.description = value or None
    elif attr == "combinator":
        if value and value not in _VALID_COMBINATORS:
            raise _ParseError(
                f"unknown combinator {value!r}; expected one of "
                f"{sorted(_VALID_COMBINATORS)}"
            )
        spec.combinator = value or None
    elif attr == "exclude_self_reviews":
        spec.exclude_self_reviews = _parse_bool(value)
    elif attr == "seed":
        spec.seed = _parse_int(value)
    elif attr == "rules_json":
        spec.rules_json = _parse_json(value, default=[])
    else:
        raise _ParseError(f"unknown session_rule_sets[] attribute {attr!r}")
    del data_type  # unused


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


def _cross_row_errors(plan: _ParsedConfig) -> list[ApplyError]:
    errors: list[ApplyError] = []
    # RuleSet-name uniqueness within the snapshot.
    seen_names: dict[str, int] = {}
    for n, spec in sorted(plan.session_rule_sets.items()):
        if not spec.name:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"session_rule_sets[{n}].name",
                    message="name is required",
                )
            )
            continue
        if spec.name in seen_names:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"session_rule_sets[{n}].name",
                    message=(
                        f"duplicate session_rule_sets name {spec.name!r} "
                        f"(also at session_rule_sets[{seen_names[spec.name]}])"
                    ),
                )
            )
        else:
            seen_names[spec.name] = n
    # Per-instrument ``rule_set_name`` resolves against either a
    # seeded RuleSet (auto-materialised on session create) or a
    # ``session_rule_sets[N]`` block in the same CSV. Pre-15B,
    # this is a validate-only check: the apply step leaves
    # ``Instrument.rule_set_id`` NULL regardless. Once 15B wires
    # the column, the resolved id will be written through.
    valid_rule_set_names = _SEEDED_RULE_SET_NAMES | set(seen_names)
    for n, instrument in sorted(plan.instruments.items()):
        if (
            instrument.rule_set_name
            and instrument.rule_set_name not in valid_rule_set_names
        ):
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"instruments[{n}].rule_set_name",
                    message=(
                        f"no such RuleSet on this session: "
                        f"{instrument.rule_set_name!r}"
                    ),
                )
            )
    # Per-response-field ``response_type`` resolves against either
    # a seeded RTD (in ``SEEDED_RESPONSE_TYPE_DEFINITIONS``) or an
    # operator-defined RTD authored earlier in the same CSV.
    valid_rtd_names = set(plan.rtds) | _SEEDED_RTD_NAMES
    for n, instrument in sorted(plan.instruments.items()):
        for m, rf in sorted(instrument.response_fields.items()):
            if rf.response_type and rf.response_type not in valid_rtd_names:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}]"
                            ".response_type"
                        ),
                        message=(
                            f"no such RTD on this session: "
                            f"{rf.response_type!r}"
                        ),
                    )
                )
    # Instrument required fields + display-/response-field required
    # fields.
    for n, instrument in sorted(plan.instruments.items()):
        if not instrument.name:
            errors.append(
                ApplyError(
                    row_number=0,
                    field=f"instruments[{n}].name",
                    message="name is required",
                )
            )
        for m, df in sorted(instrument.display_fields.items()):
            if not df.source_type:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].display_fields[{m}]"
                            ".source_type"
                        ),
                        message="source_type is required",
                    )
                )
        for m, rf in sorted(instrument.response_fields.items()):
            if not rf.field_key:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}].field_key"
                        ),
                        message="field_key is required",
                    )
                )
            if not rf.label:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}].label"
                        ),
                        message="label is required",
                    )
                )
            if not rf.response_type:
                errors.append(
                    ApplyError(
                        row_number=0,
                        field=(
                            f"instruments[{n}].response_fields[{m}]"
                            ".response_type"
                        ),
                        message="response_type is required",
                    )
                )
    return errors


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

    Empty/NULL = a per-reviewee instrument. A non-empty value is
    an ordered, comma-joined list of distinct reviewee tag keys
    (``tag_1`` / ``tag_2`` / ``tag_3``) — e.g. ``tag_1`` or
    ``tag_1,tag_2,tag_3`` — composing the group key. Returns the
    canonical (whitespace-stripped) form.
    """
    if not value:
        return None
    keys = [part.strip() for part in value.split(",")]
    invalid = [k for k in keys if k not in _VALID_GROUP_KINDS]
    if invalid or len(set(keys)) != len(keys):
        raise _ParseError(
            f"invalid instrument group_kind {value!r}; expected a comma-"
            f"joined list of distinct keys from {sorted(_VALID_GROUP_KINDS)}"
        )
    return ",".join(keys)


# --------------------------------------------------------------------------- #
# Apply phase — wipe-and-replace
# --------------------------------------------------------------------------- #


def _apply_plan(
    db: Session,
    review_session: ReviewSession,
    plan: _ParsedConfig,
    *,
    user: User | None,
    correlation_id: str | None,
) -> dict[str, int]:
    counts = {
        "session": 0,
        "email_overrides": 0,
        "rtds": 0,
        "instruments": 0,
        "display_fields": 0,
        "response_fields": 0,
        "session_rule_sets": 0,
        "field_labels": 0,
    }

    counts["session"] = _apply_session_metadata(review_session, plan)
    counts["email_overrides"] = _apply_email_overrides(review_session, plan)
    counts["rtds"] = _apply_rtds(db, review_session, plan)
    db.flush()
    counts["session_rule_sets"] = _apply_session_rule_sets(
        db, review_session, plan
    )
    db.flush()
    inst_counts = _apply_instruments(db, review_session, plan)
    counts.update(inst_counts)
    counts["field_labels"] = _apply_field_labels(db, review_session, plan)
    db.flush()

    if user is not None:
        lifecycle.invalidate_if_validated(
            db,
            review_session=review_session,
            user=user,
            reason="settings_imported",
            correlation_id=correlation_id,
        )

    audit.write_event(
        db,
        event_type="session.settings_imported",
        summary=(
            f"Imported Settings CSV for session {review_session.code}"
        ),
        actor_user_id=user.id if user is not None else None,
        session=review_session,
        payload=audit.counts(**counts),
        correlation_id=correlation_id,
    )

    return counts


def _apply_session_metadata(
    review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Apply session.* keys with the fallback rule: write the
    snapshot value only when the destination's existing field is
    empty / None.

    The single rule covers both flows naturally — on Create New
    Session, operator-typed fields are non-empty so the snapshot
    fills in only the blanks; on Session Home (existing session),
    the destination already has values so the snapshot is
    effectively read-and-ignored. ``code`` follows the same
    rule (suffix-derivation on collision is a deferred follow-on
    per the 12A-2 plan)."""

    written = 0
    overrides = plan.session_overrides
    for key in ("name", "code", "description", "deadline", "help_contact"):
        if key not in overrides:
            continue
        existing = getattr(review_session, key, None)
        if existing not in (None, ""):
            continue
        setattr(review_session, key, overrides[key])
        written += 1
    return written


def _apply_email_overrides(
    review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Replace ``email_template_overrides`` JSON wholesale from
    the parsed dict. Empty cells collapsed into "key absent" by
    the parser, so the dict is the resolver-ready shape."""

    review_session.email_template_overrides = (
        dict(plan.email_overrides) if plan.email_overrides else None
    )
    return len(plan.email_overrides)


def _apply_rtds(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Upsert operator-defined RTDs by ``response_type``; delete
    existing operator-defined rows not in the CSV. Seeded rows
    are untouched.

    Operator-defined RTD rows can be referenced by
    ``InstrumentResponseField.response_type_id`` — but the
    instruments wipe-and-replace happens after this step, so
    by-then there are no FK references to worry about. We delete
    instruments first to be safe."""

    # Need to delete instruments (and their response fields)
    # *before* deleting operator-defined RTDs the response fields
    # reference. We do that here by deferring RTD deletes until
    # after instruments are wiped — call this method twice:
    # first pass returns the spec, second pass after instruments
    # are wiped does the upsert + delete. Instead, simpler:
    # delete instruments here first, then process RTDs, then
    # re-create instruments downstream.
    # Responses FK ``assignments``; the bulk Core delete below would
    # trip that constraint on a session reverted from ``ready`` (which
    # keeps its responses) unless they go first. The settings
    # re-import rebuilds the whole instrument structure, so these
    # responses cannot survive it regardless — clear them explicitly.
    db.execute(
        Response.__table__.delete().where(
            Response.assignment_id.in_(
                select(Assignment.id).where(
                    Assignment.session_id == review_session.id
                )
            )
        )
    )
    db.execute(
        Assignment.__table__.delete().where(
            Assignment.session_id == review_session.id
        )
    )
    instruments_to_delete = (
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
        )
        .scalars()
        .all()
    )
    for instrument in instruments_to_delete:
        db.delete(instrument)
    db.flush()

    existing = {
        rtd.response_type: rtd
        for rtd in db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id,
                ResponseTypeDefinition.is_seeded.is_(False),
            )
        ).scalars()
    }

    written = 0
    for name, spec in plan.rtds.items():
        if not spec.data_type:
            # Defensive: a row that only set min/max with no
            # data_type was malformed; cross-row check should
            # have flagged it. Skip silently to avoid a NULL
            # write.
            continue
        rtd = existing.get(name)
        # Map the CSV's ``int`` / ``decimal`` / ``short_text`` /
        # ``long_text`` / ``list`` lowercase tokens to the model's
        # capitalized ``Integer`` / ``Decimal`` / ``String`` /
        # ``List`` data_type values. The export emits the lowercase
        # tokens to match the documented vocabulary.
        model_data_type = _RTD_TYPE_LOWER_TO_MODEL[spec.data_type]
        if rtd is None:
            rtd = ResponseTypeDefinition(
                session_id=review_session.id,
                response_type=name,
                data_type=model_data_type,
                min=spec.min,
                max=spec.max,
                step=spec.step,
                list_csv=spec.list_csv,
                is_seeded=False,
            )
            db.add(rtd)
        else:
            rtd.data_type = model_data_type
            rtd.min = spec.min
            rtd.max = spec.max
            rtd.step = spec.step
            rtd.list_csv = spec.list_csv
            del existing[name]
        written += 1

    # Anything left in ``existing`` was not in the CSV → delete.
    for orphan in existing.values():
        db.delete(orphan)
    db.flush()

    return written


# Map every token the importer accepts to the model's
# canonical capitalized values used by
# ``ResponseTypeDefinition.data_type``. Lowercase tokens follow
# the documented import vocabulary; capitalized tokens match
# what today's export emits directly.
_RTD_TYPE_LOWER_TO_MODEL = {
    "int": "Integer",
    "decimal": "Decimal",
    "short_text": "String",
    "long_text": "String",
    "list": "List",
    "Integer": "Integer",
    "Decimal": "Decimal",
    "String": "String",
    "List": "List",
}


def _apply_session_rule_sets(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Upsert non-seeded ``session_rule_sets`` rows by ``name``;
    delete existing non-seeded rows not in the CSV. Seeded rows
    are untouched (they auto-materialise from the seed catalogue
    on session create)."""

    existing = {
        snap.name: snap
        for snap in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
        if snap.name not in _SEEDED_RULE_SET_NAMES
    }

    written = 0
    for spec in plan.session_rule_sets.values():
        assert spec.name is not None  # cross-row check enforced
        # ``SessionRuleSet.description`` is NOT NULL — empty cell
        # ⇒ empty string, not None.
        description = spec.description or ""
        snap = existing.pop(spec.name, None)
        if snap is None:
            snap = SessionRuleSet(
                session_id=review_session.id,
                name=spec.name,
                description=description,
                combinator=spec.combinator or "ALL_OF",
                exclude_self_reviews=spec.exclude_self_reviews,
                seed=spec.seed,
                rules_json=spec.rules_json,
            )
            db.add(snap)
        else:
            snap.description = description
            snap.combinator = spec.combinator or "ALL_OF"
            snap.exclude_self_reviews = spec.exclude_self_reviews
            snap.seed = spec.seed
            snap.rules_json = spec.rules_json
        written += 1

    for orphan in existing.values():
        db.delete(orphan)
    db.flush()

    return written


def _apply_instruments(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> dict[str, int]:
    """Re-create instruments + display_fields + response_fields
    from the CSV. ``_apply_rtds`` already wiped any pre-existing
    instruments + their child rows in this same transaction."""

    counts = {
        "instruments": 0,
        "display_fields": 0,
        "response_fields": 0,
    }
    rtd_by_name = {
        rtd.response_type: rtd
        for rtd in db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id
            )
        ).scalars()
    }
    # Per-instrument rule pin (Segment 15B Slice 2b). The session-tier
    # ``session_rule_sets`` rows have been upserted by
    # ``_apply_session_rule_sets`` earlier in the apply pipeline. The
    # idempotent seed materialiser here covers any session that
    # bypassed ``sessions.create_session`` (test fixtures, raw
    # constructors) — mirrors the per-request safety net in
    # ``views.build_instruments_context``.
    materialise_seed_rule_sets(db, review_session)
    rule_set_id_by_name = {
        snap.name: snap.id
        for snap in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }

    for n in sorted(plan.instruments.keys()):
        spec = plan.instruments[n]
        assert spec.name is not None  # cross-row check enforced
        if spec.rule_set_name:
            resolved_rule_set_id = rule_set_id_by_name.get(spec.rule_set_name)
            if resolved_rule_set_id is None:
                raise _ParseError(
                    f"rule set {spec.rule_set_name!r} not found in this "
                    f"session — add it to the session's RuleSet pool first "
                    f"(instruments[{n}].rule_set_name)"
                )
        else:
            resolved_rule_set_id = None
        instrument = Instrument(
            session_id=review_session.id,
            name=spec.name,
            short_label=spec.short_label,
            description=spec.description,
            order=n,  # 1-based CSV position wins over ``order`` cell
            accepting_responses=spec.accepting_responses,
            responses_visible_when_closed=spec.responses_visible_when_closed,
            sort_display_fields=spec.sort_display_fields,
            group_kind=spec.group_kind,
            rule_set_id=resolved_rule_set_id,
        )
        db.add(instrument)
        db.flush()  # populate ``instrument.id``
        counts["instruments"] += 1

        for m in sorted(spec.display_fields.keys()):
            df_spec = spec.display_fields[m]
            assert df_spec.source_type is not None
            db.add(
                InstrumentDisplayField(
                    instrument_id=instrument.id,
                    label=df_spec.label or "",
                    source_type=df_spec.source_type,
                    source_field=df_spec.source_field or "",
                    order=m,
                    visible=df_spec.visible,
                )
            )
            counts["display_fields"] += 1

        for m in sorted(spec.response_fields.keys()):
            rf_spec = spec.response_fields[m]
            assert rf_spec.response_type is not None
            rtd = rtd_by_name.get(rf_spec.response_type)
            if rtd is None:
                raise _ApplyConflict(
                    f"unknown RTD {rf_spec.response_type!r} on this session "
                    f"(instruments[{n}].response_fields[{m}].response_type)"
                )
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=rf_spec.field_key or "",
                    label=rf_spec.label or "",
                    response_type_id=rtd.id,
                    required=rf_spec.required,
                    order=m,
                    validation=validation_block_for_rtd(rtd),
                    help_text=rf_spec.help_text,
                    help_text_visible=rf_spec.help_text_visible,
                )
            )
            counts["response_fields"] += 1

    return counts


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


class _ApplyConflict(Exception):
    """Raised by the apply phase when a cross-row reference
    can't be resolved against the in-progress session state
    (e.g. an unknown RTD reference). The caller's transaction
    handler rolls back."""
