"""Unit tests for the lifecycle enum -> display label mapping."""

from __future__ import annotations

import pytest

from app.services.lifecycle_display import (
    DISPLAY_LABELS,
    lifecycle_display_label,
)


@pytest.mark.parametrize(
    "enum_value,expected",
    [
        ("draft", "Draft"),
        ("validated", "Validated"),
        ("ready", "Activated"),
        ("expired", "Expired"),
        ("archived", "Archived"),
    ],
)
def test_lifecycle_display_label_for_known_states(
    enum_value: str, expected: str
) -> None:
    assert lifecycle_display_label(enum_value) == expected


def test_lifecycle_display_label_only_overrides_ready() -> None:
    """The mapping only diverges from ``str.capitalize`` for the
    ``ready`` enum (per spec/session_home.md). Adding any other entry
    should be a deliberate spec change, so the test pins the current
    set."""
    assert DISPLAY_LABELS == {"ready": "Activated"}


def test_lifecycle_display_label_falls_through_unknown() -> None:
    """Unknown enum values fall through capitalised so a future state
    still renders something readable until the mapping is updated."""
    assert lifecycle_display_label("hibernating") == "Hibernating"


def test_lifecycle_display_label_handles_empty_string() -> None:
    assert lifecycle_display_label("") == ""
