"""Every text-like input type a template uses is styled by `base.html`.

`body.ui-v2`'s input rule, and its `:focus` and `:focus-visible`
companions, name each input type they style. A type left off the list
renders with the browser's default box — narrower, unpadded, unbordered
— beside its styled neighbours, and nothing in the suite has a layout
engine to see it. The Settings page's App password box (19T Item 16
entry 4) and the audit log's date filters were both left off.

So this derives the types from the templates rather than listing them:
a template that starts using a new type fails here until the rule
names it, or until it is added to `NOT_TEXT_LIKE` with a reason.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "app/web/templates/base.html"
TEMPLATES = ROOT / "app/web/templates"

#: Input types that are not text boxes, so the shared rule must not
#: style them: each renders its own control.
NOT_TEXT_LIKE = {"checkbox", "radio", "hidden", "submit", "button"}

#: Types the box rule styles but the focus rules have never named. Not
#: decided here, only recorded: `file` has been off both focus lists
#: since they were written, so a keyboard user gets the browser's own
#: ring on it. Removing it from this set is the way to take that up.
FOCUS_EXEMPT = {"file"}


def _used_types() -> set[str]:
    types: set[str] = set()
    for path in TEMPLATES.rglob("*.html"):
        for tag in re.findall(r"<input\b[^>]*>", path.read_text()):
            match = re.search(r'\btype="([a-z-]+)"', tag)
            if match:
                types.add(match.group(1))
    return types - NOT_TEXT_LIKE


def _rule_types(pseudo: str) -> set[str]:
    css = BASE.read_text()
    # The selector group that ends in `body.ui-v2 select<pseudo> {`.
    match = re.search(
        r"((?:\s*body\.ui-v2 [^,{]+,)+)\s*body\.ui-v2 select"
        + re.escape(pseudo)
        + r"\s*\{",
        css,
    )
    assert match, f"no `body.ui-v2 select{pseudo}` rule in base.html"
    return set(
        re.findall(
            r'input\[type="([a-z-]+)"\]' + re.escape(pseudo) + r"(?=,)",
            match.group(1),
        )
    )


@pytest.mark.parametrize("pseudo", ["", ":focus", ":focus-visible"])
def test_every_used_text_like_type_is_in_the_rule(pseudo: str) -> None:
    used = _used_types() - (FOCUS_EXEMPT if pseudo else set())
    missing = used - _rule_types(pseudo)
    assert not missing, (
        f"input types used in templates but missing from base.html's "
        f"`body.ui-v2 input[type=…]{pseudo}` rule: {sorted(missing)}"
    )
