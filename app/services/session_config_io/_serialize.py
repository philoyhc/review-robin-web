"""Settings CSV export — ``serialize_session_config``.

Produces the deterministic ``list[Row]`` the Extract Data card
streams at ``GET /operator/sessions/{id}/export/settings.csv``.
Section ordering is pinned by the unit-test golden fixture.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    ReviewSession,
    SessionFieldLabel,
    SessionRuleSet,
)
from app.services.date_formatting import iso_in_zone
from app.services.email_templates import (
    OVERRIDE_KEYS,
    RESPONSES_RECEIVED_ENABLED_KEY,
)
# Wave 5 PR 5.2 — RuleSet seeding retired; ``_SEEDED_RULE_SETS``
# import retired.
from app.services.sessions import resolve_session_timezone

from app.services.session_config_io._rows import (
    Row,
    _bool,
    _decimal,
    _int,
    _json,
    _str,
)


# Wave 5 PR 5.2 — ``_SEEDED_RULE_SET_NAMES`` retired alongside
# the RuleSet seeding helper. The session_rule_sets export
# emits every row unconditionally.


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
        # Segment 18N PR 5 — the eight 18G scheduled-event columns
        # added 2026-05-20 (Part 0 schema) + lit up across Parts 1-3.
        # Two datetime anchors + four offset / offset-list strings +
        # the retention overrides pair. Pre-PR-5 the round-trip was
        # silently dropping every one of these on Zip-all → import.
        Row(
            "session.scheduled_activate_at",
            iso_in_zone(
                review_session.scheduled_activate_at,
                resolve_session_timezone(review_session),
            ),
            "datetime",
        ),
        Row(
            "session.responses_release_at",
            iso_in_zone(
                review_session.responses_release_at,
                resolve_session_timezone(review_session),
            ),
            "datetime",
        ),
        Row(
            "session.invite_offsets",
            _str(", ".join(review_session.invite_offsets or [])),
            "string",
        ),
        Row(
            "session.reminder_offsets",
            _str(", ".join(review_session.reminder_offsets or [])),
            "string",
        ),
        Row(
            "session.archive_offset",
            _str(review_session.archive_offset),
            "string",
        ),
        Row(
            "session.release_until_offset",
            _str(review_session.release_until_offset),
            "string",
        ),
        Row(
            "session.retention_exception",
            _bool(review_session.retention_exception),
            "boolean",
        ),
        Row(
            "session.retention_overrides",
            _json(review_session.retention_overrides or {}),
            "json",
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


# Per-session ``response_type_definitions`` table retired
# 2026-05-26 — the previous ``_rtd_rows`` exporter is gone.
# Imports of pre-retirement bundles silently ignore any ``rtds[...]``
# rows (see ``_apply.py``). Response field bounds + data_type now
# round-trip inline on each ``response_field_*`` row.


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
    # Wave 5 PR 5.2 — the un-pinned-instrument audit-log fallback
    # (``_audit_log_rule_set_name``) retired with the
    # ``operator_rule_sets`` table. Unpinned instruments export
    # with an empty rule_set_name cell — matches the behaviour for
    # sessions that never ran rule-based Generate.

    rows: list[Row] = []
    for n, instrument in enumerate(instruments, start=1):
        rows.extend(
            _instrument_rows(
                instrument,
                n,
                rule_set_name_by_id,
            )
        )
        rows.extend(_display_field_rows(instrument, n))
        rows.extend(_response_field_rows(instrument, n))
    return rows


def _instrument_rows(
    instrument: Instrument,
    n: int,
    rule_set_name_by_id: dict[int, str],
) -> list[Row]:
    prefix = f"instruments[{n}]"
    # Per-instrument selection (``Instrument.rule_set_id``, 15B)
    # wins. An un-pinned instrument exports with an empty
    # rule_set_name cell (Wave 5 PR 5.2 retired the audit-log
    # fallback that used to resolve seeded names).
    rule_set_name_value = (
        rule_set_name_by_id.get(instrument.rule_set_id)
        if instrument.rule_set_id is not None
        else None
    )
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
        # Segment 18N PR 5 — three operator-input fields that
        # pre-PR-5 didn't round-trip: drag-gripper column widths
        # (Band 2 preview table), the 18M page-break flag, and the
        # Band 2 selections / sample-reviewee pick JSON blob.
        Row(
            f"{prefix}.column_widths",
            _json(instrument.column_widths or {}),
            "json",
        ),
        Row(
            f"{prefix}.starts_new_page",
            _bool(instrument.starts_new_page),
            "boolean",
        ),
        Row(
            f"{prefix}.band2_state",
            _json(instrument.band2_state or {}),
            "json",
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
        # Segment 18N PR 5 — inline type + bounds + per-field
        # visibility. Pre-PR-5 the serializer exported the legacy
        # ``response_type`` text label but lost every semantic
        # bound after 18J Wave 2 PR iii-b4 retired the RTD table
        # and moved type / bounds inline. Round-trips through
        # ``_inline_*`` now restore the full Band 3 row state.
        rows.append(
            Row(
                f"{prefix}.data_type",
                _str(field._inline_data_type),
                "string",
            )
        )
        rows.append(
            Row(f"{prefix}.min", _decimal(field._inline_min), "decimal")
        )
        rows.append(
            Row(f"{prefix}.max", _decimal(field._inline_max), "decimal")
        )
        rows.append(
            Row(f"{prefix}.step", _decimal(field._inline_step), "decimal")
        )
        rows.append(
            Row(
                f"{prefix}.list_csv",
                _str(field._inline_list_csv),
                "string",
            )
        )
        rows.append(Row(f"{prefix}.visible", _bool(field.visible), "boolean"))
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
        # Wave 5 PR 5.1 — the 15C ``library_name`` provenance cell
        # retired alongside the operator-library tier. The
        # ``library_origin_id`` column on session_rule_sets stays
        # for now (drops in PR 5.2); no export cell.
    return rows


def _non_seeded_session_rule_sets(
    db: Session, review_session: ReviewSession
) -> list[SessionRuleSet]:
    # Wave 5 PR 5.2 — every session_rule_sets row emits now (the
    # seeded-name exclusion retired with the seeding helper).
    # Function kept by name so callers don't churn; it's effectively
    # "every session_rule_sets row for the session."
    return list(
        db.execute(
            select(SessionRuleSet)
            .where(SessionRuleSet.session_id == review_session.id)
            .order_by(SessionRuleSet.id)
        )
        .scalars()
        .all()
    )


# Wave 5 PR 5.2 — ``_audit_log_rule_set_name`` retired with the
# ``operator_rule_sets`` table it queried for the seed-name fallback.


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
