"""Unit tests for ``app.services.session_config_io`` — Segment 12A-1
PR 1 settings export.

Covers the per-section serialiser shape, the section-ordering
contract, the inert-but-included defaults (`sort_display_fields`,
`group_kind`, empty `session_rule_sets`, empty
`session_field_labels`), and the seeded-RuleSet exclusion.

The integration counterpart in
``tests/integration/test_extracts_settings_route.py`` covers the
HTTP route, audit emission, and Content-Disposition headers.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ResponseTypeDefinition,
    ReviewSession,
    SessionFieldLabel,
    SessionRuleSet,
    User,
)
from app.services.instruments import ensure_default_response_type_definitions
from app.services.session_config_io import (
    HEADER,
    Row,
    serialize_session_config,
)
from app.services.session_config_io import _ParseError, _parse_group_kind
from _legacy_rtd_helpers import (
    inline_kwargs_legacy as _inline_kwargs_legacy,
)


# Segment 18J Wave 2 PR iii-b4 — the FK from
# ``instrument_response_fields`` to ``response_type_definitions``
# retired. The Likert5 inline shape is used by field fixtures
# below.
_LIKERT_INLINE = _inline_kwargs_legacy("Likert5")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _user(db: Session, email: str = "alice@example.edu") -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _bare_session(db: Session, *, code: str = "spring") -> ReviewSession:
    """Session with seeded RTDs but no instruments / RTDs / RuleSets /
    field labels."""

    user = _user(db, email=f"op-{code}@example.edu")
    review_session = ReviewSession(
        name=code.title(),
        code=code,
        description="Two-line description.",
        deadline=dt.datetime(2026, 5, 15, 17, 0, tzinfo=dt.timezone.utc),
        help_contact="help@example.edu",
        created_by_user_id=user.id,
    )
    db.add(review_session)
    db.flush()
    ensure_default_response_type_definitions(db, review_session)
    db.flush()
    return review_session


def _row_dict(rows: list[Row]) -> dict[str, Row]:
    return {r.field: r for r in rows}


# --------------------------------------------------------------------------- #
# Section 1 — session-level rows
# --------------------------------------------------------------------------- #


def test_session_rows_emit_typed_cells(db: Session) -> None:
    review_session = _bare_session(db, code="s1")
    by_field = _row_dict(serialize_session_config(db, review_session))

    assert by_field["session.name"] == Row("session.name", "S1", "string")
    assert by_field["session.code"] == Row("session.code", "s1", "string")
    assert by_field["session.description"] == Row(
        "session.description", "Two-line description.", "string"
    )
    assert by_field["session.deadline"] == Row(
        "session.deadline", "2026-05-15T17:00:00+00:00", "datetime"
    )
    assert by_field["session.help_contact"] == Row(
        "session.help_contact", "help@example.edu", "string"
    )


def test_session_deadline_emits_in_session_zone(db: Session) -> None:
    """session.deadline exports as ISO 8601 carrying the session
    zone's offset, not a bare UTC `+00:00` (Segment 18B)."""
    review_session = _bare_session(db, code="tzc")
    review_session.display_timezone = "Asia/Singapore"
    db.flush()
    by_field = _row_dict(serialize_session_config(db, review_session))
    # 2026-05-15 17:00 UTC is 2026-05-16 01:00 in Singapore (+08).
    assert by_field["session.deadline"] == Row(
        "session.deadline", "2026-05-16T01:00:00+08:00", "datetime"
    )


def test_session_rows_handle_nullable_fields(db: Session) -> None:
    """Empty cells emit ``""`` for nullable session columns. Round-trips
    through the importer (when it lands) as ``None``."""

    user = _user(db, email="nulluser@example.edu")
    review_session = ReviewSession(
        name="NullableTest",
        code="nullable",
        description=None,
        deadline=None,
        help_contact=None,
        created_by_user_id=user.id,
    )
    db.add(review_session)
    db.flush()
    by_field = _row_dict(serialize_session_config(db, review_session))

    assert by_field["session.description"].value == ""
    assert by_field["session.deadline"].value == ""
    assert by_field["session.help_contact"].value == ""


# --------------------------------------------------------------------------- #
# Section 2 — email-template overrides
# --------------------------------------------------------------------------- #


def test_email_overrides_emit_all_keys_default_empty(db: Session) -> None:
    """Each of the 12 string keys is emitted even when the operator
    left it at default; an empty value cell is the explicit
    "no override" signal. The boolean toggle defaults to ``true``
    when absent."""

    review_session = _bare_session(db, code="emails")
    by_field = _row_dict(serialize_session_config(db, review_session))

    expected_string_keys = [
        "email_overrides.invitation.subject",
        "email_overrides.invitation.body",
        "email_overrides.invitation.cc",
        "email_overrides.invitation.bcc",
        "email_overrides.reminder.subject",
        "email_overrides.reminder.body",
        "email_overrides.reminder.cc",
        "email_overrides.reminder.bcc",
        "email_overrides.responses_received.subject",
        "email_overrides.responses_received.body",
        "email_overrides.responses_received.cc",
        "email_overrides.responses_received.bcc",
    ]
    for key in expected_string_keys:
        assert by_field[key] == Row(key, "", "string")
    assert by_field["email_overrides.responses_received.enabled"] == Row(
        "email_overrides.responses_received.enabled", "true", "boolean"
    )


def test_email_overrides_round_trip_set_values(db: Session) -> None:
    review_session = _bare_session(db, code="emailset")
    review_session.email_template_overrides = {
        "invitation_subject": "Custom subject",
        "reminder_body": "Custom body",
        "responses_received_enabled": False,
    }
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert (
        by_field["email_overrides.invitation.subject"].value
        == "Custom subject"
    )
    assert by_field["email_overrides.reminder.body"].value == "Custom body"
    assert (
        by_field["email_overrides.responses_received.enabled"].value
        == "false"
    )


# --------------------------------------------------------------------------- #
# Section 3 — operator-defined RTDs (seeded ones excluded)
# --------------------------------------------------------------------------- #


def test_seeded_rtds_are_not_emitted(db: Session) -> None:
    """Seeded RTDs auto-regenerate from
    ``SEED_RESPONSE_TYPE_DEFINITIONS`` on session create on the
    destination side; re-emitting them would either be a no-op or
    a name conflict (``uq_rtd_session_name``)."""

    review_session = _bare_session(db, code="seededrtds")
    rows = serialize_session_config(db, review_session)
    assert all(not r.field.startswith("rtds[") for r in rows)


def test_operator_defined_rtds_emit_full_row_block(db: Session) -> None:
    review_session = _bare_session(db, code="custrtds")
    db.add(
        ResponseTypeDefinition(
            session_id=review_session.id,
            response_type="GPA4",
            data_type="decimal",
            min=0.0,
            max=4.0,
            step=0.1,
            list_csv=None,
        )
    )
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert by_field["rtds[GPA4].data_type"] == Row(
        "rtds[GPA4].data_type", "decimal", "enum"
    )
    assert by_field["rtds[GPA4].min"] == Row(
        "rtds[GPA4].min", "0", "decimal"
    )
    assert by_field["rtds[GPA4].max"] == Row(
        "rtds[GPA4].max", "4", "decimal"
    )
    assert by_field["rtds[GPA4].step"] == Row(
        "rtds[GPA4].step", "0.1", "decimal"
    )
    assert by_field["rtds[GPA4].list_csv"] == Row(
        "rtds[GPA4].list_csv", "", "csv_list"
    )
    # Segment 18J Wave 2 PR iii-b3 retired the
    # ``rtds[N].library_name`` cell alongside the operator-library
    # tier. It no longer appears in the serialized output.
    assert "rtds[GPA4].library_name" not in by_field


@pytest.mark.skip(
    reason="Segment 18J Wave 2 PR iii-b3 retired the RTD library "
    "tier; the rtds[N].library_name cell is gone from the export."
)
def test_rtd_library_name_resolves_through_origin(db: Session) -> None:
    """Retired alongside the RTD library tier in iii-b3."""


def test_session_emits_display_timezone_and_self_reviews(
    db: Session,
) -> None:
    """18D export part — the Settings CSV carries the per-session
    display timezone and the self-reviews toggle."""
    review_session = _bare_session(db, code="s18d")
    review_session.display_timezone = "Asia/Singapore"
    review_session.self_reviews_active = False
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert by_field["session.display_timezone"] == Row(
        "session.display_timezone", "Asia/Singapore", "string"
    )
    assert by_field["session.self_reviews_active"] == Row(
        "session.self_reviews_active", "false", "boolean"
    )


# --------------------------------------------------------------------------- #
# Section 4 — instruments + display fields + response fields
# --------------------------------------------------------------------------- #


def _likert_id(db: Session, review_session: ReviewSession) -> int:
    return (
        db.query(ResponseTypeDefinition)
        .filter(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Likert5",
        )
        .one()
        .id
    )




def test_instrument_block_emits_canonical_fields(db: Session) -> None:
    review_session = _bare_session(db, code="instr")
    instr = Instrument(
        session_id=review_session.id,
        name="Peer evaluation",
        short_label="Peer",
        description="Mid-semester peer review",
        order=0,
        accepting_responses=True,
        responses_visible_when_closed=False,
    )
    db.add(instr)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instr.id,
            field_key="overall",
            label="Overall",
            **_LIKERT_INLINE,
            required=True,
            order=0,
            help_text="How would you rate them?",
            help_text_visible=True,
        )
    )
    db.add(
        InstrumentDisplayField(
            instrument_id=instr.id,
            label="Cohort",
            source_type="reviewee",
            source_field="tag_1",
            order=0,
            visible=True,
        )
    )
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))

    # Instrument-level rows.
    assert by_field["instruments[1].name"].value == "Peer evaluation"
    assert by_field["instruments[1].short_label"].value == "Peer"
    assert by_field["instruments[1].description"].value == (
        "Mid-semester peer review"
    )
    assert by_field["instruments[1].order"].value == "0"
    assert by_field["instruments[1].accepting_responses"].value == "true"
    assert (
        by_field["instruments[1].responses_visible_when_closed"].value
        == "false"
    )
    # Inert-but-included rows always emit defaults today.
    assert by_field["instruments[1].sort_display_fields"] == Row(
        "instruments[1].sort_display_fields", "[]", "json"
    )
    assert by_field["instruments[1].group_kind"] == Row(
        "instruments[1].group_kind", "", "enum"
    )
    assert by_field["instruments[1].rule_set_name"] == Row(
        "instruments[1].rule_set_name", "", "string"
    )

    # Display field row. The ``.label`` row was retired in
    # Segment 15A Slice 1 — per-instrument display-field labels
    # are no longer round-tripped (the resolver reads only
    # ``session_field_labels`` + built-in defaults).
    assert by_field["instruments[1].display_fields[1].source_type"].value == (
        "reviewee"
    )
    assert (
        by_field["instruments[1].display_fields[1].source_field"].value
        == "tag_1"
    )
    assert "instruments[1].display_fields[1].label" not in by_field
    assert by_field["instruments[1].display_fields[1].visible"].value == "true"

    # Response field row.
    assert (
        by_field["instruments[1].response_fields[1].field_key"].value
        == "overall"
    )
    assert by_field["instruments[1].response_fields[1].label"].value == (
        "Overall"
    )
    assert (
        by_field["instruments[1].response_fields[1].response_type"].value
        == "Likert5"
    )
    assert (
        by_field["instruments[1].response_fields[1].required"].value == "true"
    )
    assert (
        by_field["instruments[1].response_fields[1].help_text"].value
        == "How would you rate them?"
    )
    assert (
        by_field["instruments[1].response_fields[1].help_text_visible"].value
        == "true"
    )


def test_multiple_instruments_indexed_by_order_position(db: Session) -> None:
    """1-based position is the export's stable identifier; ``order``
    determines the index for instruments and ``(order, id)``
    determines the index for fields within an instrument."""

    review_session = _bare_session(db, code="multi")
    _likert_id(db, review_session)  # ensure seeded RTDs exist
    for n, name in enumerate(["First", "Second"]):
        instr = Instrument(
            session_id=review_session.id,
            name=name,
            order=n,
        )
        db.add(instr)
        db.flush()
        db.add(
            InstrumentResponseField(
                instrument_id=instr.id,
                field_key="q1",
                label="Q1",
                **_LIKERT_INLINE,
                order=0,
            )
        )
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert by_field["instruments[1].name"].value == "First"
    assert by_field["instruments[2].name"].value == "Second"


# --------------------------------------------------------------------------- #
# Section 5 — per-session RuleSets (non-seeded only)
# --------------------------------------------------------------------------- #


def test_session_rule_sets_emit_all_rows(db: Session) -> None:
    """Wave 5 PR 5.2 — the ``is_seeded`` exclusion retired with
    the RuleSet seeding helper. Every session_rule_sets row now
    emits; legacy "Full Matrix"-named rows from pre-PR-5.2
    seeded sessions are treated the same as operator-authored
    rows."""

    review_session = _bare_session(db, code="rulesets")
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="Cross-cohort fanout",
            description="Operator-authored",
            combinator="PIPELINE",
            exclude_self_reviews=False,
            seed=42,
            rules_json=[{"id": "r1", "kind": "MATCH"}],
        )
    )
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert "session_rule_sets[1].name" in by_field
    assert (
        by_field["session_rule_sets[1].name"].value == "Cross-cohort fanout"
    )

    # Field shape.
    assert (
        by_field["session_rule_sets[1].combinator"].value == "PIPELINE"
    )
    assert (
        by_field["session_rule_sets[1].exclude_self_reviews"].value == "false"
    )
    assert by_field["session_rule_sets[1].seed"].value == "42"
    assert (
        by_field["session_rule_sets[1].rules_json"].value
        == '[{"id":"r1","kind":"MATCH"}]'
    )
    assert by_field["session_rule_sets[1].rules_json"].data_type == "json"


def test_instrument_rule_set_name_resolves_through_session_rule_sets(
    db: Session,
) -> None:
    """``Instrument.rule_set_id`` is a DB-id FK; the export converts
    it to the matching ``session_rule_sets.name`` so the reference
    survives a cross-deployment hop."""

    review_session = _bare_session(db, code="rsref")
    snap = SessionRuleSet(
        session_id=review_session.id,
        name="Cross-cohort fanout",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
    )
    db.add(snap)
    db.flush()
    instr = Instrument(
        session_id=review_session.id,
        name="Pinned instrument",
        order=0,
        rule_set_id=snap.id,
    )
    db.add(instr)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instr.id,
            field_key="q1",
            label="Q1",
            **_LIKERT_INLINE,
            order=0,
        )
    )
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert by_field["instruments[1].rule_set_name"] == Row(
        "instruments[1].rule_set_name", "Cross-cohort fanout", "string"
    )


# --------------------------------------------------------------------------- #
# Section 6 — field-label overrides (Segment 15A target — table empty today)
# --------------------------------------------------------------------------- #


def test_field_labels_emit_when_present(db: Session) -> None:
    review_session = _bare_session(db, code="labels")
    db.add(
        SessionFieldLabel(
            session_id=review_session.id,
            source_type="reviewer",
            source_field="tag_1",
            label="Cohort",
        )
    )
    db.flush()

    by_field = _row_dict(serialize_session_config(db, review_session))
    assert by_field["field_labels.reviewer.tag_1"] == Row(
        "field_labels.reviewer.tag_1", "Cohort", "string"
    )


def test_empty_session_field_labels_emit_no_rows(db: Session) -> None:
    """The default — table is inert today (Segment 15A target)."""

    review_session = _bare_session(db, code="nofield")
    rows = serialize_session_config(db, review_session)
    assert all(not r.field.startswith("field_labels.") for r in rows)


# --------------------------------------------------------------------------- #
# Section ordering — diff-stable contract
# --------------------------------------------------------------------------- #


def test_section_ordering_is_deterministic(db: Session) -> None:
    """Re-export of the same session emits the same byte stream — the
    operator-facing template stays diff-stable."""

    review_session = _bare_session(db, code="order")
    instr = Instrument(
        session_id=review_session.id, name="Only", order=0
    )
    db.add(instr)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instr.id,
            field_key="q1",
            label="Q1",
            **_LIKERT_INLINE,
            order=0,
        )
    )
    db.flush()

    a = serialize_session_config(db, review_session)
    b = serialize_session_config(db, review_session)
    assert a == b

    # Spot-check the high-level section sequence.
    fields = [r.field for r in a]

    def first_index(prefix: str) -> int:
        return next(i for i, f in enumerate(fields) if f.startswith(prefix))

    # session.* → email_overrides.* → instruments.* → field_labels.*.
    assert first_index("session.") < first_index("email_overrides.")
    assert first_index("email_overrides.") < first_index("instruments[")


def test_header_constant_is_canonical_three_columns() -> None:
    """The header tuple is the contract the route prepends in front
    of the streaming payload — pinning it here means a contract
    change (4-column shape, etc.) requires deliberate test churn."""

    assert HEADER == ("field", "value", "data_type")


# --------------------------------------------------------------------------- #
# PR 1a — pre-15B audit-log fallback for rule_set_name
# --------------------------------------------------------------------------- #


def _add_instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str = "Only",
    order: int = 0,
    rule_set_id: int | None = None,
) -> Instrument:
    """Create a minimal instrument with one response field so the
    settings export has something to serialise."""

    instr = Instrument(
        session_id=review_session.id,
        name=name,
        order=order,
        rule_set_id=rule_set_id,
    )
    db.add(instr)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instr.id,
            field_key="q1",
            label="Q1",
            **_LIKERT_INLINE,
            order=0,
        )
    )
    db.flush()
    return instr


# Wave 5 PR 5.2 — the audit-log RuleSet-name fallback retired with
# the operator-library tier. The _add_rule_set /
# _stamp_assignments_generated_audit helpers and the 5
# test_audit_log_* + 1 test_post_15b_per_instrument_selection
# tests that exercised the fallback retired with it.



# --------------------------------------------------------------------------- #
# group_kind parsing — single + composite keys (Segment 13C)
# --------------------------------------------------------------------------- #


def test_parse_group_kind_empty_is_none() -> None:
    assert _parse_group_kind("") is None


def test_parse_group_kind_sentinel_round_trips() -> None:
    """The no-boundary sentinel — a group instrument with no
    boundary tag — round-trips verbatim."""
    assert _parse_group_kind("both") == "both"


def test_parse_group_kind_single_code() -> None:
    assert _parse_group_kind("r2") == "r2"
    assert _parse_group_kind("p1") == "p1"


def test_parse_group_kind_composite_code() -> None:
    """A composite boundary spec is an ordered, comma-joined list of
    distinct boundary codes; whitespace is stripped."""

    assert _parse_group_kind("r1,r2,r3") == "r1,r2,r3"
    assert _parse_group_kind("r3, p1") == "r3,p1"


def test_parse_group_kind_rejects_unknown_code() -> None:
    with pytest.raises(_ParseError):
        _parse_group_kind("r1,tag_9")


def test_parse_group_kind_rejects_duplicate_code() -> None:
    with pytest.raises(_ParseError):
        _parse_group_kind("r1,r1")
