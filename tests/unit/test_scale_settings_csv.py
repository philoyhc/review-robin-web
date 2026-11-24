"""Segment 20P Item 1 rung 4 — the Settings CSV carries a response
field's ``scale`` and ``scale_labels``: exported beside its bounds,
imported with the same shape rule the card applies, and absent from an
older bundle meaning *not a scale*."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentResponseField
from app.services.session_config_io import Row, apply_session_config, serialize_session_config

from .test_apply_session_config import _bare_session, _integer_field_rows, _user

_PREFIX = "instruments[1].response_fields[1]"


def _scale_rows(step: str = "1", labels: str = "Poor||Excellent") -> list[Row]:
    rows = [r for r in _integer_field_rows("1", step) if not r.field.endswith(".max")]
    return [
        *rows,
        Row(f"{_PREFIX}.max", "5", "decimal"),
        Row(f"{_PREFIX}.scale", "true", "boolean"),
        Row(f"{_PREFIX}.scale_labels", labels, "string"),
    ]


def _field(db: Session, session_id: int) -> InstrumentResponseField:
    return db.scalars(
        select(InstrumentResponseField).join(Instrument).where(Instrument.session_id == session_id)
    ).one()


def test_an_imported_scale_is_stored_and_reaches_validation(db: Session) -> None:
    review_session = _bare_session(db, code="csv-scale")
    result = apply_session_config(db, review_session, _scale_rows())
    assert result.ok, result.errors
    field = _field(db, review_session.id)
    assert field.scale and field.scale_labels == "Poor||Excellent"
    assert field.validation == {
        "min": 1,
        "max": 5,
        "step": 1,
        "scale": True,
        "scale_labels": ["Poor", "", "Excellent"],
    }


def test_a_scale_round_trips(db: Session) -> None:
    src = _bare_session(db, code="csv-scale-src")
    assert apply_session_config(db, src, _scale_rows(labels="Low|Mid|High")).ok
    rows = serialize_session_config(db, src)
    by_field = {r.field: r for r in rows}
    assert by_field[f"{_PREFIX}.scale"].value == "true"
    assert by_field[f"{_PREFIX}.scale"].data_type == "boolean"
    assert by_field[f"{_PREFIX}.scale_labels"].value == "Low|Mid|High"

    dst = _bare_session(db, code="csv-scale-dst")
    result = apply_session_config(db, dst, rows, user=_user(db, email="scale@e.edu"))
    assert result.errors == []
    field = _field(db, dst.id)
    assert field.scale and field.scale_labels == "Low|Mid|High"
    assert field.validation and field.validation["scale_labels"] == ["Low", "Mid", "High"]


def test_a_field_that_is_not_a_scale_exports_false_and_no_labels(db: Session) -> None:
    src = _bare_session(db, code="csv-noscale")
    assert apply_session_config(db, src, _integer_field_rows("1", "1")).ok
    by_field = {r.field: r.value for r in serialize_session_config(db, src)}
    assert by_field[f"{_PREFIX}.scale"] == "false"
    assert by_field[f"{_PREFIX}.scale_labels"] == ""
    field = _field(db, src.id)
    assert not field.scale and field.validation and "scale" not in field.validation


def test_a_scale_that_cannot_be_one_is_refused_by_name(db: Session) -> None:
    """The card's shape rule, at the scale's own cell: 1 to 5 by 3 does
    not land on Max."""
    review_session = _bare_session(db, code="csv-scale-bad")
    result = apply_session_config(db, review_session, _scale_rows(step="3"))
    assert not result.ok
    assert [(e.field, e.message) for e in result.errors] == [
        (f"{_PREFIX}.scale", "Max must be Min plus a whole number of Steps.")
    ]


def test_a_string_scale_is_refused(db: Session) -> None:
    review_session = _bare_session(db, code="csv-scale-str")
    rows = [
        Row(r.field, "String", r.data_type) if r.field.endswith(".data_type") else r
        for r in _scale_rows()
        if not r.field.endswith((".min", ".max", ".step"))
    ]
    result = apply_session_config(db, review_session, rows)
    assert [(e.field, e.message) for e in result.errors] == [
        (f"{_PREFIX}.scale", "Only an Integer or a Decimal field can be a scale.")
    ]


def test_over_long_labels_are_cut_and_extra_parts_dropped(db: Session) -> None:
    review_session = _bare_session(db, code="csv-scale-long")
    result = apply_session_config(db, review_session, _scale_rows(labels="x" * 99 + "|b|c|d"))
    assert result.ok, result.errors
    assert _field(db, review_session.id).scale_labels == "x" * 60 + "|b|c"


def test_a_bundle_without_the_attributes_imports_no_scale(db: Session) -> None:
    """A bundle exported before rung 4 says nothing of the scale; the
    field it creates is not one, whatever its bounds."""
    review_session = _bare_session(db, code="csv-scale-old")
    rows = [r for r in _scale_rows() if ".scale" not in r.field]
    assert apply_session_config(db, review_session, rows).ok
    field = _field(db, review_session.id)
    assert not field.scale and field.scale_labels is None
    assert field.validation and "scale" not in field.validation


def test_a_linked_resend_owns_the_scale_rows() -> None:
    """Codex on #4195: a linked application's re-send carries the scale,
    so its two rows are among the instrument rows it owns; without them
    the bundle would be refused as not owned."""
    from app.services.linked_instruments import owns_row

    assert owns_row(f"{_PREFIX}.scale")
    assert owns_row(f"{_PREFIX}.scale_labels")
    assert not owns_row(f"{_PREFIX}.branch_op")  # branching stays the operator's
