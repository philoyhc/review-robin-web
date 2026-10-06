"""Settings CSV round-trip for saved Data shapes (PR 6 of
the Data shaper wiring slice).

Exports a session with saved shapes via
``serialize_session_config`` and applies the row list back
to a fresh session via ``apply_session_config`` — asserts
the shapes round-trip with their portable references
(instrument by short_label, response field by field_key)
resolving to the new session's FKs.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    DataShape,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services import session_config_io


_INLINE_NUMERIC = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "100int",
    "_inline_min": 1.0,
    "_inline_max": 5.0,
    "_inline_step": 1.0,
}


def _user(db: Session, *, email: str = "op@x.edu") -> User:
    user = User(email=email, display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session, *, code: str, actor: User | None = None
) -> ReviewSession:
    actor = actor or _user(db, email=f"{code}@x.edu")
    review_session = ReviewSession(
        name="DS",
        code=code,
        created_by_user_id=actor.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(
    db: Session, review_session: ReviewSession, *, short_label: str = "Peer"
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id,
        name="Peer review",
        short_label=short_label,
    )
    db.add(instrument)
    db.flush()
    return instrument


def _field(
    db: Session, instrument: Instrument, *, field_key: str = "score"
) -> InstrumentResponseField:
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=field_key.title(),
        order=0,
        **_INLINE_NUMERIC,
    )
    db.add(field)
    db.flush()
    return field


def _seed_three_shapes(
    db: Session, review_session: ReviewSession
) -> tuple[Instrument, InstrumentResponseField]:
    instrument = _instrument(
        db, review_session, short_label="Peer Review"
    )
    field = _field(db, instrument, field_key="score")

    # Shape 1 — session-wide (no scope). Default Self-review
    # handling state (``include_self``).
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Whole roster",
            axis="reviewer",
            instrument_id=None,
            response_field_id=None,
            column_chip_slots=json.dumps(
                ["reviewer:name", "reviewer:email"]
            ),
            self_review_handling="include_self",
        )
    )
    # Shape 2 — scoped to an instrument, exclude_self chip.
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Per instrument",
            axis="reviewer",
            instrument_id=instrument.id,
            response_field_id=None,
            column_chip_slots=json.dumps(
                ["reviewer:name", "reviewer:count"]
            ),
            self_review_handling="exclude_self",
        )
    )
    # Shape 3 — scoped to a specific response field, both chip.
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Per field",
            axis="reviewee",
            instrument_id=instrument.id,
            response_field_id=field.id,
            column_chip_slots=json.dumps(
                ["reviewee:name", "reviewee:mean"]
            ),
            self_review_handling="both",
        )
    )
    db.flush()
    return instrument, field


def test_export_serialises_all_three_shape_variants(
    db: Session,
) -> None:
    review_session = _session(db, code="export")
    _seed_three_shapes(db, review_session)
    rows = session_config_io.serialize_session_config(db, review_session)
    shape_rows = [r for r in rows if r.field.startswith("data_shapes[")]
    # 8 rows per shape × 3 shapes = 24. The 8 keys are name +
    # axis + instrument_short_label + instrument (D20, the block
    # number) + response_field_key + column_chip_slots +
    # self_review_handling (PR B of the Self-review handling chip
    # slice) + include_empty_rows (PR 6 of the chip-controlled-drop
    # slice).
    assert len(shape_rows) == 24
    by_field = {r.field: r.value for r in shape_rows}
    # Shapes sorted by name → 0: Per field, 1: Per instrument,
    # 2: Whole roster.
    assert by_field["data_shapes[0].name"] == "Per field"
    assert by_field["data_shapes[1].name"] == "Per instrument"
    assert by_field["data_shapes[2].name"] == "Whole roster"
    # Portable references — instrument's short_label and
    # response field's field_key, not their FKs.
    assert (
        by_field["data_shapes[0].instrument_short_label"]
        == "Peer Review"
    )
    assert by_field["data_shapes[0].response_field_key"] == "score"
    # "Per instrument" carries the instrument ref but no field
    # ref.
    assert (
        by_field["data_shapes[1].instrument_short_label"]
        == "Peer Review"
    )
    assert by_field["data_shapes[1].response_field_key"] == ""
    # "Whole roster" carries neither.
    assert by_field["data_shapes[2].instrument_short_label"] == ""
    assert by_field["data_shapes[2].response_field_key"] == ""
    # D20 — the instrument's block number rides beside the label.
    assert by_field["data_shapes[0].instrument"] == "1"
    assert by_field["data_shapes[1].instrument"] == "1"
    assert by_field["data_shapes[2].instrument"] == ""


def test_a_shape_on_an_unlabelled_instrument_keeps_its_scope(
    db: Session,
) -> None:
    """D20 (ruled 2026-10-06): an instrument with no short label
    exports an empty label reference, which alone re-imports as
    unscoped. The block number carries the scope instead: the shape
    comes back on the instrument built from that block, with its
    field."""
    session_a = _session(db, code="d20-src")
    _instrument(db, session_a, short_label="First")
    unlabelled = _instrument(db, session_a, short_label="")
    unlabelled.order = 1
    field = _field(db, unlabelled, field_key="score")
    db.add(
        DataShape(
            session_id=session_a.id,
            name="Second's score",
            axis="reviewee",
            instrument_id=unlabelled.id,
            response_field_id=field.id,
            column_chip_slots=json.dumps(["reviewee:name"]),
        )
    )
    db.flush()
    rows = session_config_io.serialize_session_config(db, session_a)
    by_field = {r.field: r.value for r in rows}
    assert by_field["data_shapes[0].instrument_short_label"] == ""
    assert by_field["data_shapes[0].instrument"] == "2"

    session_b = _session(db, code="d20-dst")
    result = session_config_io.apply_session_config(
        db, session_b, list(rows), user=None
    )
    assert result.ok, result.errors
    db.expire_all()
    shape = db.execute(
        select(DataShape).where(DataShape.session_id == session_b.id)
    ).scalar_one()
    second = db.execute(
        select(Instrument).where(
            Instrument.session_id == session_b.id, Instrument.order == 1
        )
    ).scalar_one()
    assert shape.instrument_id == second.id
    assert shape.response_field_id == db.execute(
        select(InstrumentResponseField.id).where(
            InstrumentResponseField.instrument_id == second.id,
            InstrumentResponseField.field_key == "score",
        )
    ).scalar_one()


def test_the_instrument_row_parses_blank_or_a_number() -> None:
    """D20: the ``instrument`` row is optional and blank means none; a
    non-number is a parse error naming the row."""
    from app.services.session_config_io._apply_data_shape import (
        _apply_data_shape_kv,
    )
    from app.services.session_config_io._apply_shared import (
        _ParseError,
        _ParsedConfig,
    )

    plan = _ParsedConfig()
    _apply_data_shape_kv(plan, "data_shapes[0].name", "S", "string")
    assert plan.data_shapes[0].instrument_number is None
    _apply_data_shape_kv(plan, "data_shapes[0].instrument", "", "integer")
    assert plan.data_shapes[0].instrument_number is None
    _apply_data_shape_kv(plan, "data_shapes[0].instrument", "3", "integer")
    assert plan.data_shapes[0].instrument_number == 3
    with pytest.raises(_ParseError, match=r"data_shapes\[0\]\.instrument"):
        _apply_data_shape_kv(plan, "data_shapes[0].instrument", "x", "integer")


def _shape_rows(rows: list, *, drop: set[str] | None = None, **edits: str) -> list:
    """The bundle with ``data_shapes[0].<key>`` cells replaced by
    ``edits`` and the keys in ``drop`` removed — a hand-edited or older
    bundle."""
    out = []
    for row in rows:
        key = row.field.removeprefix("data_shapes[0].")
        if row.field.startswith("data_shapes[0].") and key in (drop or set()):
            continue
        if row.field.startswith("data_shapes[0].") and key in edits:
            row = session_config_io.Row(row.field, edits[key], row.data_type)
        out.append(row)
    return out


def _two_instrument_bundle(
    db: Session, code: str, *, labels: tuple[str, str], on: int = 1
):
    """Session with two instruments (``order`` 0 and 1) carrying
    ``labels``, ``score`` only on the one at ``order == on``, and one
    shape on that one."""
    review_session = _session(db, code=code)
    first = _instrument(db, review_session, short_label=labels[0])
    second = _instrument(db, review_session, short_label=labels[1])
    first.order, second.order = 0, 1
    target = (first, second)[on]
    field = _field(db, target, field_key="score")
    db.add(
        DataShape(
            session_id=review_session.id,
            name="Scoped",
            axis="reviewee",
            instrument_id=target.id,
            response_field_id=field.id,
            column_chip_slots=json.dumps(["reviewee:name"]),
        )
    )
    db.flush()
    return session_config_io.serialize_session_config(db, review_session)


def _imported_shape(db: Session, code: str, rows: list):
    target = _session(db, code=code)
    result = session_config_io.apply_session_config(
        db, target, list(rows), user=None
    )
    assert result.ok, result.errors
    db.expire_all()
    shape = db.execute(
        select(DataShape).where(DataShape.session_id == target.id)
    ).scalar_one()
    by_order = {
        i.order: i
        for i in db.execute(
            select(Instrument).where(Instrument.session_id == target.id)
        ).scalars()
    }
    return shape, by_order


def test_a_shared_short_label_is_settled_by_the_number(db: Session) -> None:
    """D20: two instruments share the label ``X``; the label names
    neither, so the number puts the shape — and its field — on the
    right one."""
    # On the first: a last-label-wins lookup would pick the second.
    rows = _two_instrument_bundle(db, "d20-dup", labels=("X", "X"), on=0)
    shape, by_order = _imported_shape(db, "d20-dup-dst", rows)
    assert shape.instrument_id == by_order[0].id
    assert shape.response_field_id is not None


def test_a_unique_label_wins_over_the_number(db: Session) -> None:
    """D20: the short label is the portable reference; the number is
    only the fallback, so a label that names one instrument wins even
    when a hand edit points the number elsewhere."""
    rows = _shape_rows(
        _two_instrument_bundle(db, "d20-pref", labels=("A", "B")), instrument="1"
    )
    shape, by_order = _imported_shape(db, "d20-pref-dst", rows)
    assert shape.instrument_id == by_order[1].id


def test_a_number_naming_no_block_leaves_the_shape_unscoped(db: Session) -> None:
    rows = _shape_rows(
        _two_instrument_bundle(db, "d20-miss", labels=("", "")), instrument="9"
    )
    shape, _ = _imported_shape(db, "d20-miss-dst", rows)
    assert shape.instrument_id is None
    assert shape.response_field_id is None


def test_hand_edited_block_numbers_with_gaps_still_resolve(db: Session) -> None:
    """D20: the number is matched against the bundle's own block
    numbers, so renumbering ``[1]``, ``[2]`` to ``[0]``, ``[3]`` (and the
    shape's reference with them) keeps the shape on its instrument."""
    rows = _two_instrument_bundle(db, "d20-gap", labels=("", ""))
    renumbered = [
        session_config_io.Row(
            r.field.replace("instruments[1].", "instruments[0].").replace(
                "instruments[2].", "instruments[3]."
            ),
            "3" if r.field == "data_shapes[0].instrument" else r.value,
            r.data_type,
        )
        for r in rows
    ]
    shape, by_order = _imported_shape(db, "d20-gap-dst", renumbered)
    assert shape.instrument_id == by_order[1].id
    assert shape.response_field_id is not None


def test_an_older_bundle_without_the_row_resolves_by_label(db: Session) -> None:
    """D20: a bundle exported before the row existed still imports, by
    label alone."""
    rows = _shape_rows(
        _two_instrument_bundle(db, "d20-old", labels=("A", "B")), drop={"instrument"}
    )
    assert not any(r.field == "data_shapes[0].instrument" for r in rows)
    shape, by_order = _imported_shape(db, "d20-old-dst", rows)
    assert shape.instrument_id == by_order[1].id
    assert shape.response_field_id is not None


def test_roundtrip_applies_shapes_with_portable_references(
    db: Session,
) -> None:
    """Export from session A, apply onto session B (which has
    instruments + fields with matching short_label /
    field_key), and confirm the shapes come back with the new
    session's FKs."""
    session_a = _session(db, code="src")
    _seed_three_shapes(db, session_a)
    rows = session_config_io.serialize_session_config(db, session_a)

    # Build a destination session with matching short_label /
    # field_key so the references resolve.
    session_b = _session(db, code="dst")
    instr_b = _instrument(
        db, session_b, short_label="Peer Review"
    )
    _field(db, instr_b, field_key="score")
    db.flush()

    result = session_config_io.apply_session_config(
        db, session_b, list(rows), user=None
    )
    assert result.ok, result.errors
    db.expire_all()

    shapes_b = list(
        db.execute(
            select(DataShape)
            .where(DataShape.session_id == session_b.id)
            .order_by(DataShape.name)
        ).scalars()
    )
    assert len(shapes_b) == 3
    by_name = {s.name: s for s in shapes_b}
    # Session-wide shape — FKs stay null.
    assert by_name["Whole roster"].instrument_id is None
    assert by_name["Whole roster"].response_field_id is None
    # Instrument-scoped shape — FK resolves to a session B
    # instrument whose ``short_label`` matches the serialized
    # reference. Look up by short_label rather than by the
    # ``instr_b`` Python reference: ``apply_session_config``
    # may resolve via lazy-seeding paths that create a new
    # instrument row in some flows (the SQLite default-id
    # allocation happens to line up with ``instr_b.id``;
    # Postgres exposes the indirection).
    resolved_instr_id = db.execute(
        select(Instrument.id).where(
            Instrument.session_id == session_b.id,
            Instrument.short_label == "Peer Review",
        )
    ).scalar_one()
    assert by_name["Per instrument"].instrument_id == resolved_instr_id
    assert by_name["Per instrument"].response_field_id is None
    # Field-scoped shape — FK resolves to the same instrument's
    # ``score`` field.
    resolved_field_id = db.execute(
        select(InstrumentResponseField.id).where(
            InstrumentResponseField.instrument_id == resolved_instr_id,
            InstrumentResponseField.field_key == "score",
        )
    ).scalar_one()
    assert by_name["Per field"].instrument_id == resolved_instr_id
    assert by_name["Per field"].response_field_id == resolved_field_id
    # Column slots round-trip JSON-stable.
    assert json.loads(by_name["Per field"].column_chip_slots) == [
        "reviewee:name",
        "reviewee:mean",
    ]


def test_apply_wipes_existing_shapes_before_replacing(
    db: Session,
) -> None:
    """The applier replaces (not merges) saved shapes — a
    pre-existing shape on the destination not present in the
    incoming CSV is wiped."""
    session_a = _session(db, code="repl-src")
    _seed_three_shapes(db, session_a)
    rows = session_config_io.serialize_session_config(db, session_a)

    session_b = _session(db, code="repl-dst")
    instr_b = _instrument(db, session_b, short_label="Peer Review")
    _field(db, instr_b, field_key="score")
    # Pre-existing shape on B that's NOT in the import.
    db.add(
        DataShape(
            session_id=session_b.id,
            name="Stale",
            axis="reviewer",
            instrument_id=None,
            response_field_id=None,
            column_chip_slots=json.dumps(["reviewer:name"]),
        )
    )
    db.flush()

    session_config_io.apply_session_config(
        db, session_b, list(rows), user=None
    )
    db.expire_all()

    names = {
        s.name
        for s in db.execute(
            select(DataShape).where(DataShape.session_id == session_b.id)
        ).scalars()
    }
    assert "Stale" not in names
    assert names == {"Whole roster", "Per instrument", "Per field"}


# --------------------------------------------------------------------------- #
# Self-review handling chip — PR B
# --------------------------------------------------------------------------- #


def test_self_review_handling_state_roundtrips_through_settings_csv(
    db: Session,
) -> None:
    """Each of the three chip states (``include_self`` /
    ``exclude_self`` / ``both``) survives an export → import
    round-trip via the Settings CSV. Per
    ``guide/extract_data.md`` § *Self-review handling* PR B."""
    session_a = _session(db, code="srh-src")
    _seed_three_shapes(db, session_a)
    rows = session_config_io.serialize_session_config(db, session_a)

    # Confirm the per-shape ``self_review_handling`` rows appear
    # on the export side.
    field_by_path = {r.field: r.value for r in rows}
    # Shapes sorted by name on serialize: Per field, Per
    # instrument, Whole roster.
    assert field_by_path["data_shapes[0].self_review_handling"] == "both"
    assert (
        field_by_path["data_shapes[1].self_review_handling"]
        == "exclude_self"
    )
    assert (
        field_by_path["data_shapes[2].self_review_handling"]
        == "include_self"
    )

    # Import onto a fresh session with matching short_label /
    # field_key and confirm the state survives.
    session_b = _session(db, code="srh-dst")
    instr_b = _instrument(db, session_b, short_label="Peer Review")
    _field(db, instr_b, field_key="score")
    db.flush()
    result = session_config_io.apply_session_config(
        db, session_b, list(rows), user=None
    )
    assert result.ok, result.errors
    db.expire_all()
    shapes_b = {
        s.name: s for s in db.execute(
            select(DataShape).where(DataShape.session_id == session_b.id)
        ).scalars()
    }
    assert shapes_b["Whole roster"].self_review_handling == "include_self"
    assert shapes_b["Per instrument"].self_review_handling == "exclude_self"
    assert shapes_b["Per field"].self_review_handling == "both"


def test_apply_falls_through_to_default_on_missing_self_review_handling_row(
    db: Session,
) -> None:
    """A pre-PR-B Settings CSV (no ``self_review_handling`` row)
    imports cleanly with the ``include_self`` default — today's
    behaviour preserved for chip-less exports."""
    session_a = _session(db, code="srh-legacy-src")
    _seed_three_shapes(db, session_a)
    rows = list(session_config_io.serialize_session_config(db, session_a))
    # Strip the new column from the row set to simulate a
    # pre-PR-B export.
    rows = [
        r for r in rows
        if not r.field.endswith(".self_review_handling")
    ]
    session_b = _session(db, code="srh-legacy-dst")
    instr_b = _instrument(db, session_b, short_label="Peer Review")
    _field(db, instr_b, field_key="score")
    db.flush()
    result = session_config_io.apply_session_config(
        db, session_b, rows, user=None
    )
    assert result.ok, result.errors
    db.expire_all()
    for shape in db.execute(
        select(DataShape).where(DataShape.session_id == session_b.id)
    ).scalars():
        assert shape.self_review_handling == "include_self"


def test_a_loaded_instruments_relationship_does_not_mislead_the_apply(
    db: Session,
) -> None:
    """Dc10: the apply deletes the destination's instruments and adds
    new ones without touching ``review_session.instruments``. When a
    caller has loaded that relationship first, the data-shape step read
    the deleted rows and scoped the shape to a gone id. A row in another
    session after the old one keeps SQLite from reusing that id, which
    would otherwise hide the fault."""
    source = _session(db, code="dc10-src")
    instrument = _instrument(db, source, short_label="Peer")
    field = _field(db, instrument, field_key="score")
    db.add(
        DataShape(
            session_id=source.id,
            name="Scoped",
            axis="reviewee",
            instrument_id=instrument.id,
            response_field_id=field.id,
            column_chip_slots=json.dumps(["reviewee:name"]),
        )
    )
    db.flush()
    rows = session_config_io.serialize_session_config(db, source)

    target = _session(db, code="dc10-dst")
    old = _instrument(db, target, short_label="Peer")
    _instrument(db, _session(db, code="dc10-bump"), short_label="Other")
    assert [i.id for i in target.instruments] == [old.id]

    result = session_config_io.apply_session_config(db, target, rows, user=None)
    assert result.ok, result.errors
    new = db.execute(
        select(Instrument).where(Instrument.session_id == target.id)
    ).scalar_one()
    shape = db.execute(
        select(DataShape).where(DataShape.session_id == target.id)
    ).scalar_one()
    assert new.id != old.id
    assert shape.instrument_id == new.id
    assert shape.response_field_id is not None
