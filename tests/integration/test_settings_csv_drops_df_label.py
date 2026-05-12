"""Settings-CSV retirement of ``display_fields[*].label`` — 15A Slice 1.

Pins:

- ``_display_field_rows`` no longer emits the ``.label`` row.
- ``apply_session_config`` tolerates a legacy ``.label`` row by
  silently dropping the value (so legacy exports import cleanly).
- ``InstrumentDisplayField.label`` is untouched by Settings-CSV
  round-trip after the retirement — the column stays in the
  schema as dead data and the apply phase does not overwrite a
  pre-existing value when a CSV row attempts to set one.

Sibling to ``tests/integration/test_field_labels_resolver.py``
which covers the resolver chain itself.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    ResponseTypeDefinition,
    ReviewSession,
    User,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _make_session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    return review_session, op


def _make_session_with_df(
    db: Session, code: str, *, df_label: str = ""
) -> tuple[ReviewSession, User, Instrument, InstrumentDisplayField]:
    review_session, op = _make_session(db, code)
    rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Rating",
        data_type="String",
    )
    db.add(rtd)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id, name="Survey", order=0
    )
    db.add(instrument)
    db.flush()
    df = InstrumentDisplayField(
        instrument_id=instrument.id,
        source_type="reviewee",
        source_field="tag_1",
        label=df_label,
        visible=True,
        order=2,
    )
    db.add(df)
    db.flush()
    return review_session, op, instrument, df


def test_serialize_does_not_emit_display_field_label(db: Session) -> None:
    """A display field with a per-instrument label round-trips
    *without* the ``.label`` row. Source / visible rows continue
    to round-trip as before."""
    review_session, _, _, _ = _make_session_with_df(
        db, "csv-df-noemit", df_label="legacy override"
    )
    rows = serialize_session_config(db, review_session)
    keys = {row.field for row in rows}
    assert "instruments[1].display_fields[1].source_type" in keys
    assert "instruments[1].display_fields[1].source_field" in keys
    assert "instruments[1].display_fields[1].visible" in keys
    assert "instruments[1].display_fields[1].label" not in keys


def test_apply_tolerates_legacy_display_field_label_row(
    db: Session,
) -> None:
    """A legacy Settings CSV carrying ``display_fields[N].label``
    imports cleanly — no parse error, no apply error. The value
    is silently dropped: the DB column stays at its current
    value (here, the empty seed)."""
    review_session, _, instrument, df = _make_session_with_df(
        db, "csv-df-legacy", df_label=""
    )
    # Build a minimal Settings CSV containing only the rows
    # apply_session_config needs to recognise the display field
    # plus a legacy .label row.
    rows = [
        Row(
            "instruments[1].name",
            "Survey",
            "string",
        ),
        Row(
            "instruments[1].display_fields[1].source_type",
            "reviewee",
            "enum",
        ),
        Row(
            "instruments[1].display_fields[1].source_field",
            "tag_1",
            "string",
        ),
        Row(
            "instruments[1].display_fields[1].label",
            "legacy override that should be dropped",
            "string",
        ),
        Row(
            "instruments[1].display_fields[1].visible",
            "true",
            "boolean",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.errors == []
    # The display field's label column is *not* updated to the
    # legacy value — apply silently drops it. ``apply`` is
    # wipe-and-replace so re-query rather than refreshing the
    # original instance.
    refreshed = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id,
            InstrumentDisplayField.source_type == "reviewee",
            InstrumentDisplayField.source_field == "tag_1",
        )
    ).scalar_one()
    assert refreshed.label == ""


def test_apply_rejects_unknown_field_labels_source_field(
    db: Session,
) -> None:
    """The new ``_VALID_FL_SOURCE_FIELDS`` map gates the
    per-source allowlist on import: ``reviewer.name`` is not in
    scope (reviewer has only tag_1/2/3) and parsing surfaces a
    named error."""
    review_session, _ = _make_session(db, "csv-fl-bad-src")
    rows = [
        Row(
            "field_labels.reviewer.name",
            "Should fail",
            "string",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.errors
    assert any(
        "source_field" in err.message and "reviewer" in err.message
        for err in result.errors
    )


def test_apply_accepts_new_reviewee_identity_slots(db: Session) -> None:
    """The widened allowlist accepts the new reviewee identity
    slots (``name`` / ``email_or_identifier`` / ``profile_link``)
    that 15A brings into scope."""
    review_session, _ = _make_session(db, "csv-fl-identity")
    rows = [
        Row(
            "field_labels.reviewee.name",
            "Student name",
            "string",
        ),
        Row(
            "field_labels.reviewee.email_or_identifier",
            "Student ID",
            "string",
        ),
        Row(
            "field_labels.reviewee.profile_link",
            "Photo",
            "string",
        ),
    ]
    result = apply_session_config(db, review_session, rows)
    assert result.errors == []
    assert result.counts["field_labels"] == 3
