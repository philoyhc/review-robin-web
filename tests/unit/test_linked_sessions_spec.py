"""`spec/linked_sessions.md` names every lock and every profile, and each
profile's row says what the profile takes (segment 23F close, author
2026-11-16): the page is the one reference for what a link changes,
organized by lock so another application is a profile entry plus a table
row. Derived from `app/services/linked_apps.py`, so a lock, a profile or a
profile's locks or owned settings changed there without the page fails here."""

from __future__ import annotations

import re
from pathlib import Path

from app.services import linked_apps

SPEC = Path(__file__).resolve().parents[2] / "spec" / "linked_sessions.md"


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _rows() -> dict[str, list[str]]:
    profiles = _section(SPEC.read_text(encoding="utf-8"), "Profiles")
    rows: dict[str, list[str]] = {}
    for line in profiles.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        key = re.fullmatch(r"`([a-z_]+)`", cells[0]) if cells else None
        if key:
            rows[key.group(1)] = cells
    return rows


def test_every_lock_has_its_section_in_order() -> None:
    locks = _section(SPEC.read_text(encoding="utf-8"), "The locks")
    named = re.findall(r"^### `([a-z_]+)`$", locks, flags=re.MULTILINE)
    assert named == [lock.value for lock in linked_apps.Lock]


def test_every_profile_has_its_row() -> None:
    assert sorted(_rows()) == sorted(linked_apps.LINKED_APPS)


def test_each_row_says_what_its_profile_takes() -> None:
    """The Locks cell is "all nine" for a profile taking every lock, else
    the lock values it takes; the Owned settings cell names
    `SESSION_FIELDS` exactly when the profile owns them."""
    rows = _rows()
    for key, profile in linked_apps.LINKED_APPS.items():
        _, name, locks, owned = rows[key][:4]
        assert name == profile.name, key
        if profile.locks == frozenset(linked_apps.Lock):
            assert locks == "all nine", key
        else:
            assert set(re.findall(r"`([a-z_]+)`", locks)) == {lock.value for lock in profile.locks}
        assert ("`SESSION_FIELDS`" in owned) == (
            profile.owned_settings == linked_apps.SESSION_FIELDS
        )
        has_structure = profile.has(linked_apps.Lock.INSTRUMENT_STRUCTURE)
        assert ("instrument rows" in owned) == has_structure, key
