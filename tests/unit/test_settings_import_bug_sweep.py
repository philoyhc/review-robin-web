"""Settings CSV import fixes from `guide/findings_2026-10-16_bugs.md`.

* **S3** — a ``field_key`` the card would refuse is a row error.
* **S5** — two instruments naming one rule set each get their own row.
* **S6** — a roster with rows keeps its feature toggle on.
* **S7** — a row holding a NUL character is a row error.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
    split_rows,
)


def _session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Sweep", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    rule_set_id: int | None = None,
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id,
        name=name,
        short_label=name[:8],
        rule_set_id=rule_set_id,
    )
    db.add(instrument)
    db.flush()
    db.add(
        InstrumentResponseField(
            instrument_id=instrument.id,
            field_key="score",
            label="Score",
            order=0,
            _inline_data_type="Integer",
            _inline_response_type="100int",
        )
    )
    db.flush()
    return instrument


def _exported(db: Session, code: str) -> list[Row]:
    source = _session(db, code=code)
    _instrument(db, source, name="Peer review")
    return serialize_session_config(db, source)


# ── S3 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "n,key", list(enumerate(["score]", "Score", "1score", "a-b"]))
)
def test_a_field_key_the_card_refuses_is_a_row_error(
    db: Session, n: int, key: str
) -> None:
    rows = [
        row._replace(value=key)
        if row.field.endswith(".response_fields[1].field_key")
        else row
        for row in _exported(db, f"s3-src-{n}")
    ]
    destination = _session(db, code=f"s3-dst-{n}")

    result = apply_session_config(db, destination, rows)

    assert not result.ok
    assert [e.field for e in result.errors] == [
        "instruments[1].response_fields[1].field_key"
    ]
    assert "Field key must start with a lowercase letter" in (
        result.errors[0].message
    )
    assert not db.execute(
        select(Instrument.id).where(Instrument.session_id == destination.id)
    ).first()


def test_a_valid_field_key_still_imports(db: Session) -> None:
    rows = _exported(db, "s3-ok-src")
    result = apply_session_config(db, _session(db, code="s3-ok-dst"), rows)
    assert result.ok, result.errors


# ── S5 ────────────────────────────────────────────────────────────────


def test_two_instruments_naming_one_rule_set_get_a_row_each(
    db: Session,
) -> None:
    source = _session(db, code="s5-src")
    shared = SessionRuleSet(
        session_id=source.id,
        name="Shared",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=7,
        rules_json=[],
    )
    db.add(shared)
    db.flush()
    _instrument(db, source, name="Peer review", rule_set_id=shared.id)
    _instrument(db, source, name="Self review", rule_set_id=shared.id)
    rows = serialize_session_config(db, source)
    destination = _session(db, code="s5-dst")

    result = apply_session_config(db, destination, rows)

    assert result.ok, result.errors
    instruments = db.scalars(
        select(Instrument)
        .where(Instrument.session_id == destination.id)
        .order_by(Instrument.order)
    ).all()
    rule_set_ids = [i.rule_set_id for i in instruments]
    assert None not in rule_set_ids
    assert len(set(rule_set_ids)) == 2, "each instrument owns its rule set"
    first, second = (db.get(SessionRuleSet, i) for i in rule_set_ids)
    assert first.name == "Shared"
    assert (
        second.combinator,
        second.exclude_self_reviews,
        second.seed,
        second.rules_json,
    ) == (
        first.combinator,
        first.exclude_self_reviews,
        first.seed,
        first.rules_json,
    )


# ── S6 ────────────────────────────────────────────────────────────────


def _with_toggle(rows: list[Row], key: str, value: str) -> list[Row]:
    rows = [row for row in rows if row.field != f"session.{key}"]
    return rows + [Row(f"session.{key}", value, "boolean")]


def test_the_import_keeps_observers_on_while_the_roster_has_rows(
    db: Session,
) -> None:
    rows = _with_toggle(_exported(db, "s6-obs-src"), "observers_enabled", "false")
    destination = _session(db, code="s6-obs-dst")
    destination.observers_enabled = True
    db.add(Observer(session_id=destination.id, email="o@example.org"))
    db.flush()

    result = apply_session_config(db, destination, rows)

    assert result.ok, result.errors
    assert destination.observers_enabled is True


def test_the_import_keeps_relationships_on_while_the_roster_has_rows(
    db: Session,
) -> None:
    rows = _with_toggle(
        _exported(db, "s6-rel-src"), "relationships_enabled", "false"
    )
    destination = _session(db, code="s6-rel-dst")
    destination.relationships_enabled = True
    reviewer = Reviewer(
        session_id=destination.id, name="R", email="r@example.org"
    )
    reviewee = Reviewee(
        session_id=destination.id, name="E", email_or_identifier="e@example.org"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Relationship(
            session_id=destination.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.flush()

    result = apply_session_config(db, destination, rows)

    assert result.ok, result.errors
    assert destination.relationships_enabled is True


def test_the_import_still_turns_an_empty_roster_off(db: Session) -> None:
    rows = _with_toggle(_exported(db, "s6-off-src"), "observers_enabled", "false")
    destination = _session(db, code="s6-off-dst")
    destination.observers_enabled = True
    db.flush()

    result = apply_session_config(db, destination, rows)

    assert result.ok, result.errors
    assert destination.observers_enabled is False


# ── S7 ────────────────────────────────────────────────────────────────


def test_a_settings_row_holding_a_nul_is_a_row_error() -> None:
    rows, errors = split_rows(
        [
            ["session.name", "Fine", "string"],
            ["session.description", "bad\x00value", "string"],
            ["session.help_contact", "help@example.edu", "string"],
        ]
    )

    assert [(e.row_number, e.field) for e in errors] == [
        (2, "session.description")
    ]
    assert "NUL" in errors[0].message
    # Later rows keep their numbers.
    assert [row.field for row in rows] == ["session.name", "", "session.help_contact"]
