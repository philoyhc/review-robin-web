"""Unit tests for the reviewer-surface view helpers in
``app.web.views``.

Pins the composition table on :class:`InstrumentHeading` so future
edits to the helpers are accompanied by explicit table changes here.
Per ``spec/reviewer-surface.md`` "Above the table — heading + help block".
"""

from __future__ import annotations

import pytest

from types import SimpleNamespace

from app.db.models import Instrument
from app.web.views import (
    InstrumentHeading,
    constraint_summary_for_field,
    instrument_heading,
    placeholder_for_field,
)


def _instrument(*, short_label: str | None, description: str | None) -> Instrument:
    return Instrument(
        session_id=1,
        name="Inst",
        short_label=short_label,
        description=description,
    )


# ── instrument_heading — multi-instrument cases ──────────────────────────


@pytest.mark.parametrize(
    "short_label,description,expected",
    [
        (
            "Peer review",
            "Rate teammates on collaboration.",
            InstrumentHeading(
                title="#2: Peer review",
                subtitle="Rate teammates on collaboration.",
            ),
        ),
        (
            "Peer review",
            None,
            InstrumentHeading(title="#2: Peer review", subtitle=None),
        ),
        (
            None,
            "Rate teammates on collaboration.",
            InstrumentHeading(
                title="#2",
                subtitle="Rate teammates on collaboration.",
            ),
        ),
        (
            None,
            None,
            InstrumentHeading(title="#2", subtitle=None),
        ),
    ],
)
def test_instrument_heading_multi_instrument_cases(
    short_label: str | None,
    description: str | None,
    expected: InstrumentHeading,
) -> None:
    """Multi-instrument always has a `#N` prefix in the title; the
    subtitle is the description verbatim when present."""
    inst = _instrument(short_label=short_label, description=description)
    assert (
        instrument_heading(instrument=inst, position=2, total_count=3) == expected
    )


# ── instrument_heading — single-instrument cases ─────────────────────────


@pytest.mark.parametrize(
    "short_label,description,expected",
    [
        (
            "Self-eval",
            "Reflect on your own progress.",
            InstrumentHeading(
                title="Self-eval",
                subtitle="Reflect on your own progress.",
            ),
        ),
        (
            "Self-eval",
            None,
            InstrumentHeading(title="Self-eval", subtitle=None),
        ),
        # Legacy fallback — no short_label, only description: description
        # renders as the H2 title (preserves pre-Segment-11L behaviour).
        (
            None,
            "Reflect on your own progress.",
            InstrumentHeading(
                title="Reflect on your own progress.", subtitle=None
            ),
        ),
        (
            None,
            None,
            InstrumentHeading(title=None, subtitle=None),
        ),
    ],
)
def test_instrument_heading_single_instrument_cases(
    short_label: str | None,
    description: str | None,
    expected: InstrumentHeading,
) -> None:
    inst = _instrument(short_label=short_label, description=description)
    assert (
        instrument_heading(instrument=inst, position=1, total_count=1) == expected
    )


def test_instrument_heading_treats_blank_strings_as_unset() -> None:
    """Whitespace-only short_label / description are treated as unset
    so they don't render an empty title or subtitle slot."""
    inst = _instrument(short_label="   ", description="\n\t")
    assert instrument_heading(
        instrument=inst, position=1, total_count=1
    ) == InstrumentHeading(title=None, subtitle=None)
    assert instrument_heading(
        instrument=inst, position=2, total_count=2
    ) == InstrumentHeading(title="#2", subtitle=None)


# ── placeholder_for_field ────────────────────────────────────────────────


def _field(*, data_type: str, validation: dict | None) -> SimpleNamespace:
    """A duck-typed stand-in for ``InstrumentResponseField``. The real
    model derives ``data_type`` from a related RTD row, which is more
    SQLAlchemy fixture work than ``placeholder_for_field`` warrants —
    the helper only reads ``data_type`` and ``validation``."""
    return SimpleNamespace(data_type=data_type, validation=validation)


@pytest.mark.parametrize(
    ("data_type", "validation", "expected"),
    [
        # String — `{min} to {max} char`, integers
        ("String", {"min_length": 0, "max_length": 100}, "0 to 100 char"),
        ("String", {"max_length": 2000}, "0 to 2000 char"),
        # Integer — `{min} to {max}, steps of {step}`, no decimals
        (
            "Integer",
            {"min": 1, "max": 5, "step": 1},
            "1 to 5, steps of 1",
        ),
        (
            "Integer",
            {"min": 0, "max": 100, "step": 1},
            "0 to 100, steps of 1",
        ),
        # Decimal — `{min} to {max}, steps of {step}`, one decimal place
        (
            "Decimal",
            {"min": 1.0, "max": 5.0, "step": 0.5},
            "1.0 to 5.0, steps of 0.5",
        ),
        (
            "Decimal",
            {"min": 1.0, "max": 5.0, "step": 0.1},
            "1.0 to 5.0, steps of 0.1",
        ),
        # List rows have no shape hint to surface.
        ("List", {"choices": ["Yes", "No"]}, ""),
        # Incomplete validation blocks → no placeholder rather than a
        # half-formed string.
        ("Integer", {"min": 1, "max": 5}, ""),
        ("String", {"min_length": 0}, ""),
        ("Integer", None, ""),
    ],
)
def test_placeholder_for_field_table(
    data_type: str, validation: dict | None, expected: str
) -> None:
    assert placeholder_for_field(_field(data_type=data_type, validation=validation)) == expected


# ── constraint_summary_for_field ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("data_type", "validation", "expected"),
    [
        # Integer / Decimal use dash notation (vs ``placeholder``'s ``to``).
        ("Integer", {"min": 1, "max": 5, "step": 1}, "1-5, steps of 1"),
        ("Integer", {"min": 0, "max": 100, "step": 1}, "0-100, steps of 1"),
        (
            "Decimal",
            {"min": 1.0, "max": 5.0, "step": 0.5},
            "1.0-5.0, steps of 0.5",
        ),
        # String drops the ``steps of`` suffix.
        ("String", {"min_length": 0, "max_length": 100}, "0-100 char"),
        # List rows are intentionally omitted from the summary line.
        ("List", {"choices": ["Yes", "No"]}, ""),
        ("List", {"choices": []}, ""),
        # Incomplete blocks still emit nothing rather than half-formed text.
        ("Integer", {"min": 1, "max": 5}, ""),
        ("Decimal", None, ""),
    ],
)
def test_constraint_summary_for_field_table(
    data_type: str, validation: dict | None, expected: str
) -> None:
    assert constraint_summary_for_field(_field(data_type=data_type, validation=validation)) == expected
