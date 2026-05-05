"""PR γ unit tests for the reviewer-surface view helpers in
``app.web.views``.

Pins the composition table on :class:`InstrumentHeading` and the
``page_button_label`` short-label fallback so future edits to the
helpers are accompanied by explicit table changes here. Per
``spec/reviewer-surface.md`` "Above the table — heading + help block".
"""

from __future__ import annotations

import pytest

from app.db.models import Instrument
from app.web.views import (
    InstrumentHeading,
    instrument_heading,
    page_button_label,
)


def _instrument(*, short_label: str | None, description: str | None) -> Instrument:
    return Instrument(
        session_id=1,
        name="Inst",
        short_label=short_label,
        description=description,
    )


# ── page_button_label ────────────────────────────────────────────────────


def test_page_button_label_uses_short_label_when_set() -> None:
    inst = _instrument(short_label="Self-eval", description=None)
    assert page_button_label(inst, 2) == "Page #2: Self-eval"


def test_page_button_label_falls_back_to_position_only() -> None:
    inst = _instrument(short_label=None, description="long-form copy")
    assert page_button_label(inst, 1) == "Page #1"


def test_page_button_label_treats_blank_short_label_as_unset() -> None:
    """Whitespace-only ``short_label`` is treated as unset so a stray
    space doesn't produce ``"Page #1: "`` with a dangling colon."""
    inst = _instrument(short_label="   ", description=None)
    assert page_button_label(inst, 3) == "Page #3"


# ── instrument_heading — multi-instrument cases ──────────────────────────


@pytest.mark.parametrize(
    "short_label,description,expected",
    [
        (
            "Peer review",
            "Rate teammates on collaboration.",
            InstrumentHeading(
                title="Page #2: Peer review",
                subtitle="Rate teammates on collaboration.",
            ),
        ),
        (
            "Peer review",
            None,
            InstrumentHeading(title="Page #2: Peer review", subtitle=None),
        ),
        (
            None,
            "Rate teammates on collaboration.",
            InstrumentHeading(
                title="Page #2",
                subtitle="Rate teammates on collaboration.",
            ),
        ),
        (
            None,
            None,
            InstrumentHeading(title="Page #2", subtitle=None),
        ),
    ],
)
def test_instrument_heading_multi_instrument_cases(
    short_label: str | None,
    description: str | None,
    expected: InstrumentHeading,
) -> None:
    """Multi-instrument always has a `Page #N` prefix in the title; the
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
    ) == InstrumentHeading(title="Page #2", subtitle=None)
