"""Session settings export + import — Segment 12A-1 PR 1 + 12A-3 PR 3.

Produces the Settings CSV the Extract Data card on Session Home
serves at ``GET /operator/sessions/{id}/export/settings.csv`` and
applies one back via ``apply_session_config(db, session, rows)``.
3-column ``field,value,data_type`` shape; every row class
documented in ``guide/segment_12A-1_export.md`` /
``guide/segment_12A-2_import.md`` (the import contract is kept as
historical-reference; the actual delivery is 12A-3 PR 3).

``serialize_session_config(session)`` returns a deterministic
``list[Row]`` for a fully-loaded session; the route streams it
through ``app.services.extracts.stream_csv``.
``apply_session_config(db, session, rows)`` parses + applies the
inverse, returning an ``ApplyResult`` with counts on success or
errors on validation failure.

Inclusion rule (paraphrased from the segment doc):

    Snapshot the operator's typing — every per-session
    configuration field they would otherwise have to retype to
    set up an equivalent new session. Excludes
    machine-derived state (``status``, ``assignment_mode``,
    validation reports, lifecycle stamps), reviewer-determined
    state (responses), system-emitted state (audit events),
    operator-level state (SMTP credentials, operator-library
    RTDs / RuleSets), and seeded RTDs / RuleSets that
    auto-materialise on session create.

The CSV is "fallback for what the operator would type", not a
machine-only round-trip — the order is fixed so re-exporting
the same session is byte-stable, and an operator hand-editing
the file in Excel is a supported workflow.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as _dataclass_field
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ResponseTypeDefinition,
    ReviewSession,
    RuleSet,
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
from app.services.rules.seeds import SEEDED_RULE_SETS as _SEEDED_RULE_SETS

_SEEDED_RTD_NAMES: frozenset[str] = frozenset(
    spec["response_type"] for spec in SEEDED_RESPONSE_TYPE_DEFINITIONS
)

__all__ = [
    "ApplyError",
    "ApplyResult",
    "HEADER",
    "Row",
    "apply_session_config",
    "serialize_session_config",
]


class Row(NamedTuple):
    """One CSV row in the Settings export.

    ``field`` is a stable, dotted / bracketed key path; ``value``
    is the cell's string representation (empty cell ⇒ unset on
    import); ``data_type`` is the cell's parsing rule, descriptive
    of the cell only — independent of any underlying RTD's
    ``data_type``.
    """

    field: str
    value: str
    data_type: str


# Header row emitted on every export.
HEADER: tuple[str, str, str] = ("field", "value", "data_type")


# Names of seeded RuleSets — used to filter ``session_rule_sets``
# rows on export. Seeded copies auto-materialise on the
# destination session from this same list, so re-emitting them
# would be a no-op or a name conflict (per
# ``uq_session_rule_set_session_name``).
_SEEDED_RULE_SET_NAMES: frozenset[str] = frozenset(
    rs.name for rs in _SEEDED_RULE_SETS
)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def serialize_session_config(
    db: Session, review_session: ReviewSession
) -> list[Row]:
    """Return every ``Row`` for the Settings CSV in deterministic
    order.

    Section ordering (also pinned in the unit-test golden
    fixture):

    1. Session-level rows (name → code → description → deadline →
       help_contact).
    2. Email-template overrides (invitation → reminder →
       responses_received, with subject → body → cc → bcc →
       enabled inside each kind).
    3. Operator-defined RTDs, ``(seed_order, response_type)``.
    4. Each instrument block in ``(order, id)``:
       - Instrument-level rows (incl. ``rule_set_name`` if any).
       - Display fields, ``(order, id)``.
       - Response fields, ``(order, id)``.
    5. Per-session RuleSets (non-seeded only), ``(id)``.
    6. Field-label overrides, ``(source_type, source_field)``.
    """

    rows: list[Row] = []
    rows.extend(_session_rows(review_session))
    rows.extend(_email_override_rows(review_session))
    rows.extend(_rtd_rows(db, review_session))
    rows.extend(_instrument_blocks(db, review_session))
    rows.extend(_session_rule_set_rows(db, review_session))
    rows.extend(_field_label_rows(db, review_session))
    return rows


# --------------------------------------------------------------------------- #
# Section 1 — session-level rows
# --------------------------------------------------------------------------- #


def _session_rows(review_session: ReviewSession) -> list[Row]:
    return [
        Row("session.name", _str(review_session.name), "string"),
        Row("session.code", _str(review_session.code), "string"),
        Row(
            "session.description",
            _str(review_session.description),
            "string",
        ),
        Row(
            "session.deadline",
            _datetime(review_session.deadline),
            "datetime",
        ),
        Row(
            "session.help_contact",
            _str(review_session.help_contact),
            "string",
        ),
    ]


# --------------------------------------------------------------------------- #
# Section 2 — email-template overrides
# --------------------------------------------------------------------------- #


# ``OVERRIDE_KEYS`` lists the 12 string keys in canonical order
# (invitation → reminder → responses_received, with subject →
# body → cc → bcc inside each kind). Each maps to a
# dotted-namespace key in the CSV by splitting off the trailing
# ``_<slot>``. ``responses_received_subject`` therefore becomes
# ``email_overrides.responses_received.subject``.
def _override_field(key: str) -> str:
    kind, slot = key.rsplit("_", 1)
    return f"email_overrides.{kind}.{slot}"


def _email_override_rows(review_session: ReviewSession) -> list[Row]:
    overrides = review_session.email_template_overrides or {}
    rows: list[Row] = []
    for key in OVERRIDE_KEYS:
        rows.append(
            Row(
                _override_field(key),
                _str(overrides.get(key)),
                "string",
            )
        )
    enabled = overrides.get(RESPONSES_RECEIVED_ENABLED_KEY)
    rows.append(
        Row(
            "email_overrides.responses_received.enabled",
            _bool(enabled if enabled is not None else True),
            "boolean",
        )
    )
    return rows


# --------------------------------------------------------------------------- #
# Section 3 — operator-defined RTDs
# --------------------------------------------------------------------------- #


def _rtd_rows(db: Session, review_session: ReviewSession) -> list[Row]:
    rtds = (
        db.execute(
            select(ResponseTypeDefinition)
            .where(
                ResponseTypeDefinition.session_id == review_session.id,
                ResponseTypeDefinition.is_seeded.is_(False),
            )
            .order_by(
                ResponseTypeDefinition.seed_order,
                ResponseTypeDefinition.response_type,
            )
        )
        .scalars()
        .all()
    )
    rows: list[Row] = []
    for rtd in rtds:
        prefix = f"rtds[{rtd.response_type}]"
        rows.append(Row(f"{prefix}.data_type", rtd.data_type, "enum"))
        rows.append(Row(f"{prefix}.min", _decimal(rtd.min), "decimal"))
        rows.append(Row(f"{prefix}.max", _decimal(rtd.max), "decimal"))
        rows.append(Row(f"{prefix}.step", _decimal(rtd.step), "decimal"))
        rows.append(
            Row(f"{prefix}.list_csv", _str(rtd.list_csv), "csv_list")
        )
    return rows


# --------------------------------------------------------------------------- #
# Section 4 — instruments + display fields + response fields
# --------------------------------------------------------------------------- #


def _instrument_blocks(
    db: Session, review_session: ReviewSession
) -> list[Row]:
    instruments = (
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        )
        .scalars()
        .all()
    )
    rule_set_name_by_id = _rule_set_name_lookup(db, review_session)
    # PR 1a — pre-15B fallback. Resolved once per export so a
    # multi-instrument session hits the audit table once.
    audit_log_rule_set_name = _audit_log_rule_set_name(db, review_session)

    rows: list[Row] = []
    for n, instrument in enumerate(instruments, start=1):
        rows.extend(
            _instrument_rows(
                instrument,
                n,
                rule_set_name_by_id,
                audit_log_rule_set_name,
            )
        )
        rows.extend(_display_field_rows(instrument, n))
        rows.extend(_response_field_rows(instrument, n))
    return rows


def _instrument_rows(
    instrument: Instrument,
    n: int,
    rule_set_name_by_id: dict[int, str],
    audit_log_rule_set_name: str | None,
) -> list[Row]:
    prefix = f"instruments[{n}]"
    # Per-instrument selection (post-15B) wins. Pre-15B
    # ``Instrument.rule_set_id`` is always NULL, so we fall back
    # to the seeded-RuleSet name resolved from the latest
    # ``assignments.generated`` audit row (PR 1a). When neither
    # source resolves, the cell stays empty — matches today's
    # behaviour for sessions that never ran rule-based Generate.
    if instrument.rule_set_id is not None:
        rule_set_name_value = rule_set_name_by_id.get(instrument.rule_set_id)
    else:
        rule_set_name_value = audit_log_rule_set_name
    rows = [
        Row(f"{prefix}.name", _str(instrument.name), "string"),
        Row(
            f"{prefix}.short_label",
            _str(instrument.short_label),
            "string",
        ),
        Row(
            f"{prefix}.description",
            _str(instrument.description),
            "string",
        ),
        Row(f"{prefix}.order", _int(instrument.order), "integer"),
        Row(
            f"{prefix}.accepting_responses",
            _bool(instrument.accepting_responses),
            "boolean",
        ),
        Row(
            f"{prefix}.responses_visible_when_closed",
            _bool(instrument.responses_visible_when_closed),
            "boolean",
        ),
        Row(
            f"{prefix}.sort_display_fields",
            _json(instrument.sort_display_fields or []),
            "json",
        ),
        Row(
            f"{prefix}.group_kind",
            _str(instrument.group_kind),
            "enum",
        ),
        Row(
            f"{prefix}.rule_set_name",
            _str(rule_set_name_value),
            "string",
        ),
    ]
    return rows


def _display_field_rows(instrument: Instrument, n: int) -> list[Row]:
    rows: list[Row] = []
    fields = sorted(instrument.display_fields, key=lambda f: (f.order, f.id))
    for m, field in enumerate(fields, start=1):
        prefix = f"instruments[{n}].display_fields[{m}]"
        rows.append(Row(f"{prefix}.source_type", field.source_type, "enum"))
        rows.append(
            Row(f"{prefix}.source_field", _str(field.source_field), "string")
        )
        # ``label`` row retired in Segment 15A Slice 1. The per-
        # instrument override capability went away with the
        # session-wide friendly-label resolver; the model column
        # stays as dead data and the apply phase tolerates legacy
        # ``label`` rows but silently drops them.
        rows.append(Row(f"{prefix}.visible", _bool(field.visible), "boolean"))
    return rows


def _response_field_rows(instrument: Instrument, n: int) -> list[Row]:
    rows: list[Row] = []
    fields = sorted(
        instrument.response_fields, key=lambda f: (f.order, f.id)
    )
    for m, field in enumerate(fields, start=1):
        prefix = f"instruments[{n}].response_fields[{m}]"
        rows.append(Row(f"{prefix}.field_key", _str(field.field_key), "string"))
        rows.append(Row(f"{prefix}.label", _str(field.label), "string"))
        rows.append(
            Row(
                f"{prefix}.response_type",
                _str(field.response_type),
                "string",
            )
        )
        rows.append(Row(f"{prefix}.required", _bool(field.required), "boolean"))
        rows.append(Row(f"{prefix}.help_text", _str(field.help_text), "string"))
        rows.append(
            Row(
                f"{prefix}.help_text_visible",
                _bool(field.help_text_visible),
                "boolean",
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Section 5 — per-session RuleSets (non-seeded only)
# --------------------------------------------------------------------------- #


def _session_rule_set_rows(
    db: Session, review_session: ReviewSession
) -> list[Row]:
    """Operator-authored ``session_rule_sets`` rows. Seeded ones
    (name-matches ``SEEDS`` from ``app.services.rules.seeds``) are
    excluded — they auto-materialise from the same constant on the
    destination session, so re-emitting them would no-op against
    ``uq_session_rule_set_session_name`` (Segment 13A-2)."""

    snapshots = _non_seeded_session_rule_sets(db, review_session)
    rows: list[Row] = []
    for n, snap in enumerate(snapshots, start=1):
        prefix = f"session_rule_sets[{n}]"
        rows.append(Row(f"{prefix}.name", _str(snap.name), "string"))
        rows.append(
            Row(f"{prefix}.description", _str(snap.description), "string")
        )
        rows.append(Row(f"{prefix}.combinator", snap.combinator, "enum"))
        rows.append(
            Row(
                f"{prefix}.exclude_self_reviews",
                _bool(snap.exclude_self_reviews),
                "boolean",
            )
        )
        rows.append(Row(f"{prefix}.seed", _int(snap.seed), "integer"))
        rows.append(
            Row(
                f"{prefix}.rules_json",
                _json(snap.rules_json or []),
                "json",
            )
        )
    return rows


def _non_seeded_session_rule_sets(
    db: Session, review_session: ReviewSession
) -> list[SessionRuleSet]:
    return [
        snap
        for snap in db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .order_by(SessionRuleSet.id)
        )
        .scalars()
        .all()
        if snap.name not in _SEEDED_RULE_SET_NAMES
    ]


def _audit_log_rule_set_name(
    db: Session, review_session: ReviewSession
) -> str | None:
    """Pre-15B fallback for ``instruments[N].rule_set_name``.

    Reads the latest ``assignments.generated`` audit row for
    ``review_session``, resolves ``detail.refs.rule_set_id`` against
    ``operator_rule_sets`` (the workspace-tier ``RuleSet`` model),
    and returns the row's ``name`` **only when it's a seed**
    (``is_seed=True``).

    Returns ``None`` when:

    - the session has no ``assignments.generated`` audit row
      (operator never ran a rule-based Generate);
    - the audit row has no ``refs.rule_set_id`` (e.g. a manual-mode
      generation that wrote the same event_type without a RuleSet
      reference);
    - the referenced ``operator_rule_sets`` row no longer exists;
    - the referenced row is a Personal-library RuleSet
      (``is_seed=False``) — Personal-library portability is
      out of scope for 12A-1, see "Pre-15B / pre-15C transient
      gap" in the segment doc.

    Once 15B + 15C ship and ``Instrument.rule_set_id`` becomes the
    populated source of truth, this fallback only applies to
    instruments whose per-instrument selection is still NULL.
    """

    audit_row = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "assignments.generated",
        )
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if audit_row is None or not audit_row.detail:
        return None
    refs = audit_row.detail.get("refs") or {}
    rule_set_id = refs.get("rule_set_id")
    if rule_set_id is None:
        return None
    rule_set = db.execute(
        select(RuleSet).where(RuleSet.id == rule_set_id)
    ).scalar_one_or_none()
    if rule_set is None or not rule_set.is_seed:
        return None
    return rule_set.name


def _rule_set_name_lookup(
    db: Session, review_session: ReviewSession
) -> dict[int, str]:
    """Map every ``session_rule_sets.id`` in this session to its
    name. Used to translate ``Instrument.rule_set_id`` (DB-id FK)
    into the export's name-based reference. Includes seeded rows
    too — an instrument may point at a seeded copy, and the
    destination session will have the same-named seed materialised
    by ``materialise_seed_rule_sets`` (15C Slice 1)."""

    return {
        row.id: row.name
        for row in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }


# --------------------------------------------------------------------------- #
# Section 6 — field-label overrides (Segment 15A target)
# --------------------------------------------------------------------------- #


def _field_label_rows(
    db: Session, review_session: ReviewSession
) -> list[Row]:
    labels = (
        db.execute(
            select(SessionFieldLabel)
            .where(SessionFieldLabel.session_id == review_session.id)
            .order_by(
                SessionFieldLabel.source_type, SessionFieldLabel.source_field
            )
        )
        .scalars()
        .all()
    )
    return [
        Row(
            f"field_labels.{lbl.source_type}.{lbl.source_field}",
            _str(lbl.label),
            "string",
        )
        for lbl in labels
    ]


# --------------------------------------------------------------------------- #
# Cell formatters
# --------------------------------------------------------------------------- #


def _str(value: str | None) -> str:
    if value is None:
        return ""
    return str(value)


def _bool(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)


def _decimal(value: float | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _datetime(value: object | None) -> str:
    if value is None:
        return ""
    # SQLite's DateTime column drops tzinfo on readback (Postgres
    # preserves it). Normalise naive readbacks to UTC so the
    # export shape is stable across both dialects.
    if isinstance(value, datetime) and value.tzinfo is None:
        from datetime import timezone

        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()  # type: ignore[union-attr]


def _json(value: object) -> str:
    """Compact, key-stable JSON. ``sort_keys=True`` keeps re-export
    bytes identical for the same logical content."""

    return json.dumps(value, separators=(",", ":"), sort_keys=True)


# =========================================================================== #
# Import side — Segment 12A-3 PR 3
# =========================================================================== #
#
# ``apply_session_config(db, session, rows) -> ApplyResult`` parses a
# Settings CSV (3-column ``field,value,data_type`` shape) and applies
# the result to ``session`` as a wipe-and-replace. Two-phase: parse +
# validate first (collect every error before reporting), then apply in
# a single transaction.
#
# Reachable only via Quick Setup slot 4 (graduated in 12A-3 PR 4) —
# no standalone Manage page. The lifecycle gate
# (``status in {"draft", "validated"}``) lives at the route layer.


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
        if value and value not in _VALID_GROUP_KINDS:
            raise _ParseError(
                f"unknown instrument group_kind {value!r}; expected one of "
                f"{sorted(_VALID_GROUP_KINDS)}"
            )
        instrument.group_kind = value or None
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

    for n in sorted(plan.instruments.keys()):
        spec = plan.instruments[n]
        assert spec.name is not None  # cross-row check enforced
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
            rule_set_id=None,  # 15B target; pre-15B left NULL
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
