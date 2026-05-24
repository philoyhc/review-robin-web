"""Settings CSV export — ``serialize_session_config``.

Produces the deterministic ``list[Row]`` the Extract Data card
streams at ``GET /operator/sessions/{id}/export/settings.csv``.
Section ordering is pinned by the unit-test golden fixture.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    ResponseTypeDefinition,
    ReviewSession,
    RuleSet,
    SessionFieldLabel,
    SessionRuleSet,
)
from app.services.date_formatting import iso_in_zone
from app.services.email_templates import (
    OVERRIDE_KEYS,
    RESPONSES_RECEIVED_ENABLED_KEY,
)
from app.services.rules.seeds import SEEDED_RULE_SETS as _SEEDED_RULE_SETS
from app.services.sessions import resolve_session_timezone

from app.services.session_config_io._rows import (
    Row,
    _bool,
    _decimal,
    _int,
    _json,
    _str,
)


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

    1. Session-level rows (name → code → description →
       display_timezone → deadline → help_contact →
       self_reviews_active).
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
        # The per-session display timezone — sits before the
        # deadline it scopes. Without it a ported session would
        # fall back to the importing operator's default zone.
        Row(
            "session.display_timezone",
            _str(review_session.display_timezone),
            "string",
        ),
        Row(
            "session.deadline",
            iso_in_zone(
                review_session.deadline,
                resolve_session_timezone(review_session),
            ),
            "datetime",
        ),
        Row(
            "session.help_contact",
            _str(review_session.help_contact),
            "string",
        ),
        # Master self-review toggle — load-bearing for assignment
        # generation (self-review pairs are gated on it).
        Row(
            "session.self_reviews_active",
            _bool(review_session.self_reviews_active),
            "boolean",
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
        # Segment 18J Wave 2 PR iii-b3 — the per-RTD library_name
        # cell retired with the operator library tier. The importer
        # still ignores it for back-compat with pre-iii-b3 CSVs.
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
    # Un-pinned-instrument fallback. Resolved once per export so a
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
    # Per-instrument selection (``Instrument.rule_set_id``, 15B)
    # wins. An un-pinned instrument (NULL ``rule_set_id``) falls
    # back to the seeded-RuleSet name resolved from the latest
    # ``assignments.generated`` audit row. When neither source
    # resolves, the cell stays empty — matches behaviour for
    # sessions that never ran rule-based Generate.
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
        # 15C library provenance — see _rtd_rows. Export leg only.
        rows.append(
            Row(
                f"{prefix}.library_name",
                _str(snap.library_origin.name if snap.library_origin else None),
                "string",
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
    """Un-pinned-instrument fallback for ``instruments[N].rule_set_name``.

    Post-15B ``Instrument.rule_set_id`` is the source of truth for
    a pinned instrument; this fallback only fires for an instrument
    whose ``rule_set_id`` is still NULL (never pinned). It reads the
    latest ``assignments.generated`` audit row for ``review_session``,
    resolves ``detail.refs.rule_set_id`` against ``operator_rule_sets``
    (the workspace-tier ``RuleSet`` model), and returns the row's
    ``name`` **only when it's a seed** (``is_seed=True``).

    Returns ``None`` when:

    - the session has no ``assignments.generated`` audit row
      (operator never ran a rule-based Generate);
    - the audit row has no ``refs.rule_set_id`` (e.g. a manual-mode
      generation that wrote the same event_type without a RuleSet
      reference);
    - the referenced ``operator_rule_sets`` row no longer exists;
    - the referenced row is a Personal-library RuleSet
      (``is_seed=False``) — Personal-library portability is
      out of scope here.
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
