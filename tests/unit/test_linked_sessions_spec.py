"""`spec/linked_sessions.md` names every lock and every profile (segment 23F
close, author 2026-11-16): the page is the one reference for what a link
changes, organized by lock so another application is a profile entry plus a
table row. Derived from `app/services/linked_apps.py`, so a lock or a profile
added there without its section or row fails here."""

from __future__ import annotations

import re
from pathlib import Path

from app.services import linked_apps

SPEC = Path(__file__).resolve().parents[2] / "spec" / "linked_sessions.md"


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_every_lock_has_its_section_in_order() -> None:
    locks = _section(SPEC.read_text(encoding="utf-8"), "The locks")
    named = re.findall(r"^### `([a-z_]+)`$", locks, flags=re.MULTILINE)
    assert named == [lock.value for lock in linked_apps.Lock]


def test_every_profile_has_its_row() -> None:
    profiles = _section(SPEC.read_text(encoding="utf-8"), "Profiles")
    rows = re.findall(r"^\|\s*`([a-z_]+)`\s*\|", profiles, flags=re.MULTILINE)
    assert sorted(rows) == sorted(linked_apps.LINKED_APPS)
