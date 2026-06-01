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
        ("expired", "Closed"),
        ("archived", "Archived"),
    ],
)
def test_lifecycle_display_label_for_known_states(
    enum_value: str, expected: str
) -> None:
    assert lifecycle_display_label(enum_value) == expected


def test_lifecycle_display_label_overrides_are_locked_in() -> None:
    """The mapping diverges from ``str.capitalize`` only for the
    two enums where the raw label reads poorly to operators
    (per spec/session_home.md + the operator-lobby "Closed"
    rename). Adding any other entry should be a deliberate spec
    change, so the test pins the current set."""
    assert DISPLAY_LABELS == {"ready": "Activated", "expired": "Closed"}


def test_lifecycle_display_label_falls_through_unknown() -> None:
    """Unknown enum values fall through capitalised so a future state
    still renders something readable until the mapping is updated."""
    assert lifecycle_display_label("hibernating") == "Hibernating"


def test_lifecycle_display_label_handles_empty_string() -> None:
    assert lifecycle_display_label("") == ""
