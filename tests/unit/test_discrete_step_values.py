"""The Data shaper's Discrete-steps qualifier.

Moved here from ``test_extract_data_route_helpers.py`` at `NF-25`,
when the function itself moved out of the route module. There were
two copies — the route's and the file-gen side's — and the gate
they compared against was a named constant in one and a literal
``12`` in the other. Equal at the time, and free to drift the
moment either was edited.

The threshold cases below now derive their boundaries from
``DISCRETE_STEPS_THRESHOLD`` rather than restating ``12``, so this
file cannot become the third place that has to be changed by hand.
"""

from __future__ import annotations

from app.db.models import InstrumentResponseField
from app.services.extracts.data_shape_extract import (
    DISCRETE_STEPS_THRESHOLD,
    discrete_step_values,
)


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
    assert discrete_step_values(field) == ["1", "2", "3", "4", "5"]


def test_integer_field_without_explicit_step_defaults_to_1() -> None:
    field = _make_field(data_type="Integer", mn=0.0, mx=3.0, step=None)
    assert discrete_step_values(field) == ["0", "1", "2", "3"]


def test_decimal_field_with_step_emits_formatted_values() -> None:
    field = _make_field(data_type="Decimal", mn=0.0, mx=1.0, step=0.5)
    assert discrete_step_values(field) == ["0", "0.5", "1"]


def test_oversized_field_returns_empty() -> None:
    # An order of magnitude past the cap, whatever the cap is.
    field = _make_field(
        data_type="Integer",
        mn=0.0,
        mx=float(DISCRETE_STEPS_THRESHOLD * 10),
        step=1.0,
    )
    assert discrete_step_values(field) == []


def test_at_threshold_field_qualifies() -> None:
    """Exactly ``DISCRETE_STEPS_THRESHOLD`` entries — the last
    width that still earns the chip."""
    field = _make_field(
        data_type="Integer",
        mn=0.0,
        mx=float(DISCRETE_STEPS_THRESHOLD - 1),
        step=1.0,
    )
    assert len(discrete_step_values(field)) == DISCRETE_STEPS_THRESHOLD


def test_just_past_threshold_skipped() -> None:
    """One more entry than the cap allows."""
    field = _make_field(
        data_type="Integer",
        mn=0.0,
        mx=float(DISCRETE_STEPS_THRESHOLD),
        step=1.0,
    )
    assert discrete_step_values(field) == []


def test_non_numeric_returns_empty() -> None:
    field = _make_field(data_type="String", mn=0.0, mx=5.0, step=1.0)
    assert discrete_step_values(field) == []


def test_missing_min_or_max_returns_empty() -> None:
    field = _make_field(data_type="Integer", mn=None, mx=5.0, step=1.0)
    assert discrete_step_values(field) == []
    field = _make_field(data_type="Integer", mn=0.0, mx=None, step=1.0)
    assert discrete_step_values(field) == []


def test_zero_or_negative_step_returns_empty() -> None:
    field = _make_field(data_type="Decimal", mn=0.0, mx=5.0, step=0.0)
    assert discrete_step_values(field) == []
    field = _make_field(data_type="Decimal", mn=0.0, mx=5.0, step=-0.5)
    assert discrete_step_values(field) == []


# --------------------------------------------------------------------- #
# The duplication itself
# --------------------------------------------------------------------- #


def test_the_arithmetic_has_exactly_one_home() -> None:
    """No second copy of this computation anywhere in ``app/``.

    `NF-25` was not "a function in the wrong layer" — it was two
    functions with the same body and different gates, one of which
    was named ``_discrete_step*s*_values`` and the other
    ``_discrete_step_values``, a single character apart. Neither
    grep nor review caught it for however long it stood.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "app"
    definers = [
        path
        for path in root.rglob("*.py")
        if re.search(r"^def _?discrete_steps?_values\(", path.read_text(), re.M)
    ]
    assert len(definers) == 1, (
        "expected one definition, found: "
        + ", ".join(str(p) for p in definers)
    )
    assert definers[0].name == "data_shape_extract.py", (
        f"the implementation moved to {definers[0]}"
    )


def test_no_literal_threshold_survives_beside_the_constant() -> None:
    """The gate derives from ``DISCRETE_STEPS_THRESHOLD``.

    ``constitution.md``: constant-derived gates only. The old
    route-side copy compared against its own constant and the
    service copy against a bare ``12``; this pins that only the
    named form remains.
    """
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parents[2]
        / "app/services/extracts/data_shape_extract.py"
    ).read_text()
    assert "count > DISCRETE_STEPS_THRESHOLD" in src
    assert "count > 12" not in src
