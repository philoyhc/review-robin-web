"""Unit + round-trip tests for ``apply_session_config`` —
Segment 12A-3 PR 3.

Covers the parse + apply contract, validation errors, and the
two round-trip invariants pinned in the 12A-2 plan:

1. Byte-stable re-export from the same session
   (``serialize → apply(self) → serialize``).
2. State-equivalent extract-import-extract across two sessions
   (modulo the ``session.name`` / ``session.code`` fallback).

The integration counterpart in
``tests/integration/test_import_config_route.py`` covers the
HTTP route, lifecycle gate, and audit emission.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services.instruments import ensure_default_response_type_definitions
from app.services.session_config_io import (
    ApplyError,
    HEADER,
    Row,
    apply_session_config,
    serialize_session_config,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _user(db: Session, *, email: str = "alice@example.edu") -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session, *, code: str, user: User | None = None, **kwargs
) -> ReviewSession:
    user = user or _user(db, email=f"op-{code}@example.edu")
    review_session = ReviewSession(
        name=kwargs.get("name", code.title()),
        code=code,
        description=kwargs.get("description"),
        deadline=kwargs.get("deadline"),
        help_contact=kwargs.get("help_contact"),
        created_by_user_id=user.id,
    )
    db.add(review_session)
    db.flush()
    ensure_default_response_type_definitions(db, review_session)
    db.flush()
    return review_session


def _bare_session(db: Session, *, code: str = "rt") -> ReviewSession:
    return _session(
        db,
        code=code,
        description="Two-line description.",
        deadline=dt.datetime(2026, 5, 15, 17, 0, tzinfo=dt.timezone.utc),
        help_contact="help@example.edu",
    )


def _populate_session_with_realistic_config(
    db: Session, review_session: ReviewSession
) -> None:
    """Add an operator-defined RTD, two instruments, display +
    response fields, an email-template override, and a
    non-seeded session_rule_sets row. Mirror the kind of session
    we want round-trips to exercise."""

    # Operator-defined RTD.
    gpa = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="GPA4",
        data_type="Decimal",
        min=0.0,
        max=4.0,
        step=0.1,
        list_csv=None,
        is_seeded=False,
    )
    db.add(gpa)
    seeded_likert = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Likert5",
        )
    ).scalar_one()
    db.flush()

    # Two instruments.
    instrument_1 = Instrument(
        session_id=review_session.id,
        name="Mid-semester eval",
        short_label="Mid",
        description="Midterm peer eval.",
        order=1,
        accepting_responses=True,
        responses_visible_when_closed=False,
        sort_display_fields=None,
        group_kind=None,
    )
    instrument_2 = Instrument(
        session_id=review_session.id,
        name="End-of-term eval",
        short_label="End",
        description=None,
        order=2,
        accepting_responses=False,
        responses_visible_when_closed=True,
        sort_display_fields=None,
        group_kind=None,
    )
    db.add(instrument_1)
    db.add(instrument_2)
    db.flush()

    db.add(
        InstrumentDisplayField(
            instrument_id=instrument_1.id,
            label="Reviewee name",
            source_type="reviewee",
            source_field="name",
            order=1,
            visible=True,
        )
    )
    db.add(
        InstrumentResponseField(
            instrument_id=instrument_1.id,
            field_key="overall",
            label="Overall rating",
            response_type_id=seeded_likert.id,
            required=True,
            order=1,
            help_text="Pick one.",
            help_text_visible=True,
        )
    )
    db.add(
        InstrumentResponseField(
            instrument_id=instrument_1.id,
            field_key="gpa",
            label="GPA",
            response_type_id=gpa.id,
            required=False,
            order=2,
            help_text=None,
            help_text_visible=True,
        )
    )

    # Email-template override + responses_received_enabled flag.
    review_session.email_template_overrides = {
        "invitation_subject": "Custom invitation subject",
        "responses_received_enabled": False,
    }

    # Non-seeded session_rule_sets row.
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="Personal Round-Robin",
            description="Each reviewer reviews the next.",
            combinator="ALL_OF",
            exclude_self_reviews=True,
            seed=42,
            rules_json=[],
        )
    )

    db.flush()


# --------------------------------------------------------------------------- #
# Parse-phase validation
# --------------------------------------------------------------------------- #


def test_unknown_data_type_token_rejected_per_row(db: Session) -> None:
    review_session = _bare_session(db, code="bad-dt")
    rows = [
        Row("session.name", "X", "string"),
        Row("session.code", "Y", "weirdtype"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any(
        "unknown data_type" in e.message and e.row_number == 2
        for e in result.errors
    )


def test_unknown_rtd_reference_rejected(db: Session) -> None:
    review_session = _bare_session(db, code="bad-rtd")
    rows = [
        Row("instruments[1].name", "Eval", "string"),
        Row(
            "instruments[1].response_fields[1].field_key",
            "f1",
            "string",
        ),
        Row(
            "instruments[1].response_fields[1].label",
            "Field 1",
            "string",
        ),
        Row(
            "instruments[1].response_fields[1].response_type",
            "NonExistent",
            "string",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any("no such RTD" in e.message for e in result.errors)


def test_unknown_rule_set_name_rejected(db: Session) -> None:
    review_session = _bare_session(db, code="bad-ruleset")
    rows = [
        Row("instruments[1].name", "Eval", "string"),
        Row(
            "instruments[1].rule_set_name",
            "Nonexistent RuleSet",
            "string",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any("no such RuleSet" in e.message for e in result.errors)


def test_seeded_rule_set_name_resolves(db: Session) -> None:
    """An ``instruments[N].rule_set_name`` referencing a seeded
    RuleSet (auto-materialised on session create) resolves to the
    matching ``session_rule_sets.id`` and pins it on the instrument
    (Segment 15B Slice 2b — pre-15B left ``rule_set_id`` NULL)."""

    review_session = _bare_session(db, code="seed-rs")
    rows = [
        Row("instruments[1].name", "Eval", "string"),
        Row("instruments[1].rule_set_name", "Full Matrix", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    full_matrix = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Full Matrix",
        )
    ).scalar_one()
    assert instrument.rule_set_id == full_matrix.id


def test_csv_rule_set_name_resolves_to_authored_block(db: Session) -> None:
    """An ``instruments[N].rule_set_name`` pointing at a
    ``session_rule_sets[M]`` block authored earlier in the same CSV
    resolves to the upserted ``session_rule_sets.id``."""

    review_session = _bare_session(db, code="csv-rs")
    rows = [
        Row("session_rule_sets[1].name", "Cohort A", "string"),
        Row("session_rule_sets[1].combinator", "ALL_OF", "enum"),
        Row("session_rule_sets[1].exclude_self_reviews", "true", "boolean"),
        Row("session_rule_sets[1].rules_json", "[]", "json"),
        Row("instruments[1].name", "Eval", "string"),
        Row("instruments[1].rule_set_name", "Cohort A", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    cohort_a = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Cohort A",
        )
    ).scalar_one()
    assert instrument.rule_set_id == cohort_a.id


def test_empty_rule_set_name_leaves_pin_null(db: Session) -> None:
    """Empty / missing ``rule_set_name`` leaves the pin NULL — the
    "no rule picked yet" state."""

    review_session = _bare_session(db, code="empty-rs")
    rows = [
        Row("instruments[1].name", "Eval", "string"),
        Row("instruments[1].rule_set_name", "", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    assert instrument.rule_set_id is None


def test_duplicate_session_rule_set_name_rejected(db: Session) -> None:
    review_session = _bare_session(db, code="dup-rs")
    rows = [
        Row("session_rule_sets[1].name", "Personal A", "string"),
        Row("session_rule_sets[1].combinator", "ALL_OF", "enum"),
        Row("session_rule_sets[2].name", "Personal A", "string"),
        Row("session_rule_sets[2].combinator", "ANY_OF", "enum"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any(
        "duplicate session_rule_sets" in e.message for e in result.errors
    )


def test_required_instrument_name_rejected(db: Session) -> None:
    review_session = _bare_session(db, code="no-name")
    rows = [
        Row("instruments[1].short_label", "Eval", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any(
        e.field == "instruments[1].name" and "required" in e.message
        for e in result.errors
    )


def test_malformed_boolean_rejected(db: Session) -> None:
    review_session = _bare_session(db, code="bad-bool")
    rows = [
        Row("instruments[1].name", "Eval", "string"),
        Row(
            "instruments[1].accepting_responses", "yesplz", "boolean"
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any("expected boolean" in e.message for e in result.errors)


def test_malformed_json_rejected(db: Session) -> None:
    review_session = _bare_session(db, code="bad-json")
    rows = [
        Row(
            "session_rule_sets[1].name",
            "Personal",
            "string",
        ),
        Row(
            "session_rule_sets[1].combinator", "ALL_OF", "enum"
        ),
        Row(
            "session_rule_sets[1].rules_json", "{not json", "json"
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert not result.ok
    assert any("expected JSON" in e.message for e in result.errors)


# --------------------------------------------------------------------------- #
# Apply phase
# --------------------------------------------------------------------------- #


def test_apply_writes_metadata_only_to_empty_destination(
    db: Session,
) -> None:
    """The fallback rule fills in only blank fields. An existing
    session with non-empty name / code keeps them; only blanks
    take the snapshot value."""

    review_session = _session(db, code="dest-existing")  # bare, no metadata
    rows = [
        Row("session.name", "Imported Name", "string"),
        Row("session.code", "imported", "string"),
        Row("session.description", "Imported description", "string"),
        Row("session.help_contact", "i@example.edu", "string"),
    ]
    apply_session_config(db, review_session, rows)
    db.refresh(review_session)
    # name + code already populated by the fixture → kept.
    assert review_session.name == "Dest-Existing"
    assert review_session.code == "dest-existing"
    # description + help_contact were None → snapshot fills in.
    assert review_session.description == "Imported description"
    assert review_session.help_contact == "i@example.edu"


def test_apply_force_applies_display_timezone_and_self_reviews(
    db: Session,
) -> None:
    """18D export part — display_timezone + self_reviews_active are
    session *config*, not operator-typed identity: the importer
    force-applies them over a destination that already holds
    (default) values, unlike the empty-only name/code fallback."""

    review_session = _bare_session(db, code="cfg-force")
    review_session.display_timezone = "UTC"
    review_session.self_reviews_active = True
    db.flush()

    rows = [
        Row("session.display_timezone", "Asia/Singapore", "string"),
        Row("session.self_reviews_active", "false", "boolean"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors
    db.refresh(review_session)
    assert review_session.display_timezone == "Asia/Singapore"
    assert review_session.self_reviews_active is False


def test_apply_library_name_cells_always_clone(db: Session) -> None:
    """18D import part — the `…library_name` provenance cells are
    recognised and skipped (not rejected), and the imported RTD is
    **always a standalone clone**: `library_origin_id` stays NULL,
    never linked to a destination-operator library entry. The
    link-vs-clone decision (2026-05-17) is always-clone."""

    review_session = _bare_session(db, code="libname")
    rows = [
        Row("rtds[GPA4].data_type", "decimal", "enum"),
        Row("rtds[GPA4].library_name", "GPA4 (library)", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors

    rtd = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "GPA4",
        )
    ).scalar_one()
    assert rtd.library_origin_id is None


def test_apply_replaces_email_overrides_wholesale(db: Session) -> None:
    review_session = _bare_session(db, code="emails")
    review_session.email_template_overrides = {
        "invitation_subject": "old subject",
        "reminder_body": "old body",
    }
    db.flush()
    rows = [
        Row(
            "email_overrides.invitation.subject",
            "new subject",
            "string",
        ),
        Row("email_overrides.invitation.body", "", "string"),
        Row(
            "email_overrides.responses_received.enabled",
            "false",
            "boolean",
        ),
    ]
    apply_session_config(db, review_session, rows)
    db.refresh(review_session)
    overrides = review_session.email_template_overrides or {}
    assert overrides.get("invitation_subject") == "new subject"
    # Old reminder_body retired (wipe-and-replace).
    assert "reminder_body" not in overrides
    assert overrides.get("responses_received_enabled") is False


def test_apply_upserts_rtds_and_deletes_orphans(db: Session) -> None:
    review_session = _bare_session(db, code="rtdupsert")
    db.add(
        ResponseTypeDefinition(
            session_id=review_session.id,
            response_type="OldRTD",
            data_type="Integer",
            min=0,
            max=10,
            step=1,
            list_csv=None,
            is_seeded=False,
        )
    )
    db.flush()

    rows = [
        Row("rtds[NewRTD].data_type", "decimal", "enum"),
        Row("rtds[NewRTD].min", "0", "decimal"),
        Row("rtds[NewRTD].max", "5", "decimal"),
        Row("rtds[NewRTD].step", "0.5", "decimal"),
        Row("rtds[NewRTD].list_csv", "", "csv_list"),
    ]
    apply_session_config(db, review_session, rows)
    db.expire_all()
    operator_rtds = (
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id,
                ResponseTypeDefinition.is_seeded.is_(False),
            )
        )
        .scalars()
        .all()
    )
    names = sorted(rtd.response_type for rtd in operator_rtds)
    assert names == ["NewRTD"]


def test_apply_recreates_instruments_and_drops_assignments(
    db: Session,
) -> None:
    """Wipe-and-replace: any pre-existing instruments + their
    assignments are dropped before the CSV's instruments are
    re-created."""

    review_session = _bare_session(db, code="instwipe")
    likert = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_session.id,
            ResponseTypeDefinition.response_type == "Likert5",
        )
    ).scalar_one()
    pre_existing = Instrument(
        session_id=review_session.id,
        name="Old instrument",
        order=1,
        accepting_responses=False,
        responses_visible_when_closed=False,
    )
    db.add(pre_existing)
    db.flush()

    rows = [
        Row("instruments[1].name", "New instrument", "string"),
        Row("instruments[1].order", "1", "integer"),
        Row(
            "instruments[1].accepting_responses", "true", "boolean"
        ),
        Row(
            "instruments[1].responses_visible_when_closed",
            "false",
            "boolean",
        ),
        Row(
            "instruments[1].response_fields[1].field_key",
            "score",
            "string",
        ),
        Row(
            "instruments[1].response_fields[1].label",
            "Score",
            "string",
        ),
        Row(
            "instruments[1].response_fields[1].response_type",
            "Likert5",
            "string",
        ),
        Row(
            "instruments[1].response_fields[1].required",
            "true",
            "boolean",
        ),
    ]
    apply_session_config(db, review_session, rows)
    db.expire_all()

    instruments = (
        db.execute(
            select(Instrument).where(
                Instrument.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )
    assert [i.name for i in instruments] == ["New instrument"]
    assert instruments[0].response_fields[0].field_key == "score"
    assert instruments[0].response_fields[0].response_type_id == likert.id


def test_apply_emits_settings_imported_audit_event(db: Session) -> None:
    review_session = _bare_session(db, code="auditemit")
    user = _user(db, email="auditor@example.edu")
    rows = [Row("instruments[1].name", "X", "string")]
    apply_session_config(db, review_session, rows, user=user)
    db.expire_all()

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.settings_imported",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = event.detail.get("counts", {})
    assert counts.get("instruments") == 1
    assert counts.get("response_fields") == 0


def test_apply_invalidates_validated_session(db: Session) -> None:
    review_session = _bare_session(db, code="invalidate")
    review_session.status = "validated"
    db.flush()
    user = _user(db, email="i@example.edu")

    rows = [Row("instruments[1].name", "Eval", "string")]
    apply_session_config(db, review_session, rows, user=user)
    db.refresh(review_session)
    assert review_session.status == "draft"


# --------------------------------------------------------------------------- #
# Round-trip contracts
# --------------------------------------------------------------------------- #


def test_round_trip_byte_stable_self_apply(db: Session) -> None:
    """Export → apply (same session) → export is byte-identical.
    Pins the contract that the importer is the inverse of the
    exporter for the export's own output."""

    review_session = _bare_session(db, code="rtself")
    _populate_session_with_realistic_config(db, review_session)

    before_rows = serialize_session_config(db, review_session)
    result = apply_session_config(db, review_session, before_rows)
    assert result.ok, result.errors
    db.expire_all()
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rtself")
    ).scalar_one()
    after_rows = serialize_session_config(db, review_session)
    assert after_rows == before_rows


def test_round_trip_state_equivalent_across_sessions(db: Session) -> None:
    """Export from A → apply to fresh B → export from B equals A
    modulo the ``session.name`` / ``session.code`` fallback rule
    (B's existing name/code win over A's snapshot values)."""

    op = _user(db, email="op-rt@example.edu")
    a = _session(
        db,
        code="rtA",
        user=op,
        description="A description",
        deadline=dt.datetime(2026, 5, 15, 17, 0, tzinfo=dt.timezone.utc),
        help_contact="a@example.edu",
    )
    _populate_session_with_realistic_config(db, a)

    b = _session(db, code="rtB", user=op)

    a_rows = serialize_session_config(db, a)
    result = apply_session_config(db, b, a_rows)
    assert result.ok, result.errors
    db.expire_all()
    b = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rtB")
    ).scalar_one()
    b_rows = serialize_session_config(db, b)

    # Exclude the two fallback fields from the comparison (B's
    # name/code are "RtB" / "rtB", not A's "RtA" / "rtA").
    fallback_fields = {"session.name", "session.code"}

    def _comparable(rows: list[Row]) -> list[Row]:
        return [r for r in rows if r.field not in fallback_fields]

    assert _comparable(b_rows) == _comparable(a_rows)


def test_empty_rules_json_round_trips_unchanged(db: Session) -> None:
    """A RuleSet with ``rules_json=[]`` round-trips without
    diffing — the export emits ``[]`` and the importer accepts
    it as the no-rules default."""

    review_session = _bare_session(db, code="rj")
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="Empty",
            combinator="ALL_OF",
            exclude_self_reviews=False,
            seed=None,
            rules_json=[],
        )
    )
    db.flush()
    before = serialize_session_config(db, review_session)
    result = apply_session_config(db, review_session, before)
    assert result.ok, result.errors
    db.expire_all()
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rj")
    ).scalar_one()
    after = serialize_session_config(db, review_session)
    assert after == before


# --------------------------------------------------------------------------- #
# Trivia
# --------------------------------------------------------------------------- #


def test_apply_result_dataclass_basics() -> None:
    ok = type("Ctx", (), {})()
    del ok  # silence linter
    error = ApplyError(row_number=1, field="x", message="m")
    assert error.row_number == 1
    assert error.message == "m"


def test_header_constant_matches_export() -> None:
    assert HEADER == ("field", "value", "data_type")


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #


def test_unknown_field_paths_are_silently_ignored(db: Session) -> None:
    """Forward-compat: unknown keys (e.g. a future export that
    adds a new section) are skipped rather than rejected, so an
    older importer still applies a newer export's known keys."""

    review_session = _bare_session(db, code="forward")
    rows = [
        Row("session.name", "X", "string"),
        Row("future_section[1].newkey", "ignored", "string"),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors


def test_field_labels_round_trip(db: Session) -> None:
    review_session = _bare_session(db, code="fl")
    rows = [
        Row(
            "field_labels.reviewer.tag_1",
            "Mentor",
            "string",
        ),
        Row(
            "field_labels.pair_context.1",
            "Cohort",
            "string",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors
    db.expire_all()
    after = serialize_session_config(db, review_session)
    label_rows = [r for r in after if r.field.startswith("field_labels.")]
    assert len(label_rows) == 2


def test_json_rules_apply_writes_through(db: Session) -> None:
    review_session = _bare_session(db, code="jsw")
    rules_payload = [{"kind": "match", "field": "tag_1"}]
    rows = [
        Row(
            "session_rule_sets[1].name",
            "WithRules",
            "string",
        ),
        Row(
            "session_rule_sets[1].combinator", "ALL_OF", "enum"
        ),
        Row(
            "session_rule_sets[1].rules_json",
            json.dumps(rules_payload),
            "json",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.ok, result.errors
    db.expire_all()
    snap = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "WithRules",
        )
    ).scalar_one()
    assert snap.rules_json == rules_payload


def test_apply_session_config_clears_responses_without_fk_error(
    db: Session,
) -> None:
    """A settings re-import on a session that still holds reviewer
    responses (e.g. one reverted from ``ready``) must not trip the
    ``responses`` foreign key on the bulk assignment delete.

    A settings re-import rebuilds the instrument structure, so those
    responses cannot survive it — ``apply_session_config`` clears them
    explicitly before the bulk delete instead of crashing.
    """
    review_session = _bare_session(db, code="resp-reimport")
    rtd = (
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id
            )
        )
        .scalars()
        .first()
    )
    instrument = Instrument(
        session_id=review_session.id, name="Eval", order=1
    )
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="score",
        label="Score",
        response_type_id=rtd.id,
    )
    reviewer = Reviewer(
        session_id=review_session.id, name="Al", email="al@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Cy",
        email_or_identifier="cy@example.edu",
    )
    db.add_all([field, reviewer, reviewee])
    db.flush()
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="4",
        )
    )
    db.flush()

    rows = serialize_session_config(db, review_session)
    # Must not raise sqlalchemy.exc.IntegrityError.
    result = apply_session_config(db, review_session, rows)
    assert result.ok

    # The re-import rebuilt the instrument structure; the responses
    # tied to the old structure are cleared.
    assert db.execute(select(Response)).all() == []
