"""Every text-like input type a template uses is styled by `base.html`.

`body.ui-v2`'s input rule, and its `:focus` and `:focus-visible`
companions, name each input type they style. A type left off the box
rule renders with the browser's default box — narrower, unpadded, with
the browser's own border — beside its styled neighbors; one left off a
focus rule takes the browser's own focus ring instead of the app's.
Nothing in the suite has a layout engine to see either. The Settings
page's App password box and the audit log's date filters were left off
the box rule, and `file` off both focus rules (19T Item 16 entries 4
and 5).

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
    missing = _used_types() - _rule_types(pseudo)
    assert not missing, (
        f"input types used in templates but missing from base.html's "
        f"`body.ui-v2 input[type=…]{pseudo}` rule: {sorted(missing)}"
    )


@pytest.mark.parametrize("pseudo", [":focus", ":focus-visible"])
def test_focus_rules_name_every_type_the_box_rule_does(pseudo: str) -> None:
    """`spec/ui_elements.md` §8: both focus rules name every input type
    the text-input rule does, used by a template today or not."""
    assert _rule_types(pseudo) == _rule_types("")
