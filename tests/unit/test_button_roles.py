"""The button roles UX refinements Item 11 moved stay moved.

Item 11 retired the filled-amber `.btn.danger-solid`: its recoverable
buttons took the amber outline (`.btn.alert`), Regenerate & prepare
took Destructive, and every banner Cancel took Secondary
(`spec/ui_elements.md` §5a, §6). Most of those buttons render only in
a lifecycle state an integration test would have to build, so this
reads the template source instead: each named button keeps its class,
and the retired class and tokens stay out of `app/`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "web" / "templates"

_ELEMENT = re.compile(r"<(button|a)\b([^>]*)>(.*?)</\1>", re.S)
_CLASS = re.compile(r'class="([^"]*)"')
_TAG = re.compile(r"<[^>]+>")


def _buttons(template: str) -> list[tuple[str, str]]:
    """Every `<button>` / `<a>` in the template as (label, class)."""
    source = (TEMPLATES / template).read_text(encoding="utf-8")
    found = []
    for match in _ELEMENT.finditer(source):
        label = " ".join(_TAG.sub(" ", match.group(3)).split())
        cls = _CLASS.search(match.group(2))
        found.append((label, cls.group(1) if cls else ""))
    return found


MOVED = [
    ("operator/partials/next_action_card.html", "Archive session", "btn alert"),
    ("operator/partials/next_action_card.html", "Regenerate &amp; prepare",
     "btn destructive"),
    ("operator/session_validate.html", "Acknowledge and activate", "btn alert"),
    ("operator/sessions_list.html", "Purge and archive", "btn alert"),
    ("operator/sessions_list.html", "Purge and archive all", "btn alert"),
    ("operator/session_extract_data.html",
     "{% if is_archived %}Already archived{% else %}Purge and archive{% endif %}",
     "btn alert"),
]


@pytest.mark.parametrize(("template", "label", "cls"), MOVED)
def test_each_moved_button_keeps_its_role(
    template: str, label: str, cls: str
) -> None:
    classes = [c for text, c in _buttons(template) if text == label]
    assert classes == [cls], (template, label, classes)


def test_every_cancel_is_secondary() -> None:
    """§5a: a banner's Cancel is Secondary, and so is every other one."""
    off = []
    seen = 0
    for path in sorted(TEMPLATES.rglob("*.html")):
        template = str(path.relative_to(TEMPLATES))
        for label, cls in _buttons(template):
            if label == "Cancel":
                seen += 1
                if cls.split()[:2] != ["btn", "secondary"]:
                    off.append(f"{template}: {cls!r}")
    assert seen >= 8, seen  # the eight banner Cancels at least
    assert not off, off


def test_the_filled_amber_stays_retired() -> None:
    hits = [
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "app").rglob("*"))
        if path.suffix in {".html", ".py"}
        and re.search(r"danger-solid|--btn-alert-", path.read_text(encoding="utf-8"))
    ]
    assert not hits, hits
