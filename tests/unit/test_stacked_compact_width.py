"""Segment 20K — the stacked layout's box widths.

A width is computed only where it is calculable (the author,
2026-11-11): a String field, a number field missing a bound and a
Decimal field missing its step take a text box; a bounded number and a
list take the compact width, the widest need among them, never under
three characters.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.db.models import InstrumentResponseField
from app.web.views import stacked_box_chars, stacked_compact_ch


def _field(data_type: str, **validation: Any) -> InstrumentResponseField:
    return InstrumentResponseField(_inline_data_type=data_type, validation=validation or None)


@pytest.mark.parametrize(
    ("field", "chars"),
    [
        (_field("Integer", min=1, max=5, step=1), 1),
        (_field("Integer", min=0, max=100, step=5), 3),
        (_field("Integer", min=-10, max=10, step=1), 3),
        # The wider bound's whole part, its sign included: -1 is two, 100 three.
        (_field("Integer", min=-1, max=100, step=1), 3),
        (_field("Integer", min=-100, max=1, step=1), 4),
        (_field("Decimal", min=0, max=10, step=0.25), 5),
        (_field("Decimal", min=0, max=1, step=0.1), 3),
        (_field("Decimal", min=0.5, max=9.5, step=1), 3),
        (_field("List", choices=["Red", "Yellow"]), 9),
        (_field("List"), 4),
    ],
)
def test_a_calculable_need(field: InstrumentResponseField, chars: int) -> None:
    assert stacked_box_chars(field) == chars


@pytest.mark.parametrize(
    "field",
    [
        _field("String", max_length=2000),
        _field("String"),
        _field("Integer", min=1, step=1),
        _field("Integer", max=5),
        _field("Decimal"),
        _field("Decimal", min=0, max=10),
    ],
)
def test_an_incalculable_width_is_a_text_box(field: InstrumentResponseField) -> None:
    assert stacked_box_chars(field) is None


def test_an_integer_with_bounds_but_no_step_is_still_compact() -> None:
    # Its values are whole, so its width needs no step.
    assert stacked_box_chars(_field("Integer", min=1, max=10)) == 2


def test_the_compact_width_is_the_widest_need_plus_padding() -> None:
    fields = [
        _field("Integer", min=1, max=5, step=1),
        _field("Decimal", min=0, max=10, step=0.25),
        _field("String", max_length=200),
    ]
    assert stacked_compact_ch(fields) == 5 + 3


def test_the_compact_width_is_never_under_three_characters() -> None:
    assert stacked_compact_ch([_field("Integer", min=1, max=5, step=1)]) == 3 + 3


def test_no_compact_field_means_no_compact_width() -> None:
    assert stacked_compact_ch([_field("String"), _field("Decimal", min=0, max=1)]) is None
    assert stacked_compact_ch([]) is None
