"""Unit tests for the small helpers in
``app.web.routes_operator._extract_data`` — currently just
``_discrete_steps_values``, the Data shaper Discrete-steps
qualifier.
"""

from __future__ import annotations

from app.db.models import InstrumentResponseField
from app.web.routes_operator._extract_data import _discrete_steps_values


def _make_field(
    *,
    data_type: str | None,
    mn: float | None = None,
    mx: float | None = None,
    step: float | None = None,
) -> InstrumentResponseField:
    return InstrumentResponseField(
        instrument_id=1,
        field_key="f",
        label="F",
        order=0,
        _inline_data_type=data_type,
        _inline_response_type="dummy",
        _inline_min=mn,
        _inline_max=mx,
        _inline_step=step,
    )


def test_integer_field_1_to_5_yields_five_steps() -> None:
    field = _make_field(data_type="Integer", mn=1.0, mx=5.0, step=1.0)
    assert _discrete_steps_values(field) == ["1", "2", "3", "4", "5"]


def test_integer_field_without_explicit_step_defaults_to_1() -> None:
    field = _make_field(data_type="Integer", mn=0.0, mx=3.0, step=None)
    assert _discrete_steps_values(field) == ["0", "1", "2", "3"]


def test_decimal_field_with_step_emits_formatted_values() -> None:
    field = _make_field(data_type="Decimal", mn=0.0, mx=1.0, step=0.5)
    assert _discrete_steps_values(field) == ["0", "0.5", "1"]


def test_oversized_field_returns_empty() -> None:
    # 0..100 step 1 ⇒ 101 entries, past the 12-cap.
    field = _make_field(data_type="Integer", mn=0.0, mx=100.0, step=1.0)
    assert _discrete_steps_values(field) == []


def test_at_threshold_field_qualifies() -> None:
    # 0..11 step 1 ⇒ 12 entries (boundary).
    field = _make_field(data_type="Integer", mn=0.0, mx=11.0, step=1.0)
    assert len(_discrete_steps_values(field)) == 12


def test_just_past_threshold_skipped() -> None:
    # 0..12 step 1 ⇒ 13 entries.
    field = _make_field(data_type="Integer", mn=0.0, mx=12.0, step=1.0)
    assert _discrete_steps_values(field) == []


def test_non_numeric_returns_empty() -> None:
    field = _make_field(data_type="String", mn=0.0, mx=5.0, step=1.0)
    assert _discrete_steps_values(field) == []


def test_missing_min_or_max_returns_empty() -> None:
    field = _make_field(data_type="Integer", mn=None, mx=5.0, step=1.0)
    assert _discrete_steps_values(field) == []
    field = _make_field(data_type="Integer", mn=0.0, mx=None, step=1.0)
    assert _discrete_steps_values(field) == []


def test_zero_or_negative_step_returns_empty() -> None:
    field = _make_field(data_type="Decimal", mn=0.0, mx=5.0, step=0.0)
    assert _discrete_steps_values(field) == []
    field = _make_field(data_type="Decimal", mn=0.0, mx=5.0, step=-0.5)
    assert _discrete_steps_values(field) == []
