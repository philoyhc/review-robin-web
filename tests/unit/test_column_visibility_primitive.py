"""One column-visibility implementation, not five — Segment 19I Item 11.

Four operator templates carried a byte-for-byte copy of the same
IIFE, differing only in a storage key and a table id: 224 lines
between them. Porting the mechanism to Invitations and Responses
would have made six copies, so it moved to ``base.html`` on the same
declarative shape the sort primitive already uses.

These are structural assertions over the template sources. They exist
because the failure mode is silent: a sixth copy would work fine, and
nothing else in the suite would notice.
"""
from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
BASE = TEMPLATES / "base.html"
OPERATOR = TEMPLATES / "operator"

# The pages that drive column-visibility chips today.
CHIP_PAGES = [
    "session_reviewers.html",
    "session_reviewees.html",
    "session_relationships.html",
    "session_assignments.html",
]

# The storage key each page has always used. Renaming one silently
# resets every operator's saved columns on that page, so the keys are
# pinned rather than merely documented.
STORAGE_KEYS = {
    "session_reviewers.html": "rrw-reviewer-tag-visibility",
    "session_reviewees.html": "rrw-reviewee-tag-visibility",
    "session_relationships.html": "rrw-relationship-tag-visibility",
    "session_assignments.html": "rrw-assignment-col-visibility",
}

# The line that actually hides a column. Exactly one implementation of
# it may exist, and it must be the shared one.
TOGGLE = 'classList.toggle("col-hidden-"'


def test_base_html_carries_the_only_implementation() -> None:
    assert BASE.read_text().count(TOGGLE) == 1


@pytest.mark.parametrize(
    "name", sorted(p.name for p in OPERATOR.glob("*.html"))
)
def test_no_operator_template_reimplements_the_toggle(name: str) -> None:
    """The assertion that would fail on a fifth copy."""
    assert TOGGLE not in (OPERATOR / name).read_text()


@pytest.mark.parametrize("name", CHIP_PAGES)
def test_each_chip_page_declares_the_primitive(name: str) -> None:
    src = (OPERATOR / name).read_text()
    key = STORAGE_KEYS[name]
    # The key rides on the table...
    assert f'data-rrw-col-toggles="{key}"' in src
    # ...and every chip row points at a table.
    assert 'data-col-toggles-for="' in src
    # ...and the chips themselves are unchanged.
    assert "data-col-toggle=" in src


@pytest.mark.parametrize("name", CHIP_PAGES)
def test_storage_keys_are_unchanged(name: str) -> None:
    """Pinned deliberately: a rename is invisible in review and resets
    every operator's saved column state on that page."""
    assert STORAGE_KEYS[name] in (OPERATOR / name).read_text()


def test_the_shared_sketch_cannot_collide_with_real_markup() -> None:
    """``base.html`` ships its own comment into every rendered
    document. The sketch therefore uses placeholder slot and table
    names — an earlier version used real ones and broke an unscoped
    assertion in ``test_reviewers_profile_link.py``, which searched the
    whole page for a CSS class name.
    """
    base = BASE.read_text()
    for real in STORAGE_KEYS.values():
        assert real not in base
    for real_slot in ("tag-1", "tag-2", "tag-3", "rt1", "et1", "p1"):
        assert f'data-col-toggle="{real_slot}"' not in base
