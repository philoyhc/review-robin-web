"""The filter-strip shape is declared once, unscoped.

Eight instances across seven Setup pages. It used to be re-declared
inside every card that held it, which meant moving the markup from one
card to another silently dropped whatever only that card supplied.
19P.1 did it twice — `is-locked` (a half-typed row could be thrown away
by a stray click on `Search`) and then `margin-top` (the buttons sat
flush against the search box at 0px). Neither was visible to the suite:
it has no layout engine and CSS reach is not markup.

So this guards the *architecture* rather than any one declaration. A
scope that re-declares a base property is how the trap comes back, and
these tests fail on that rather than on the symptom two dev-slot cycles
later.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[2] / "app/web/templates/base.html"

#: The declarations the base owns. A scope re-stating one of these is
#: either redundant or an undocumented divergence; both are the bug.
BASE_OWNED = ("align-items", "justify-content", "flex-wrap", "margin-top")

#: What each scope is allowed to narrow, and why. Adding to this list is
#: a deliberate act; that is the point of it being a list.
ALLOWED_NARROWINGS = {
    ".operator-actions-card": {"flex"},          # status squeezed to ~1/5
    # Half-width pane: tighter gaps, smaller/subtler labels. Plus
    # `flex-direction`, which is the <=860px rule stacking the row —
    # a half-width pane runs out of room for two controls sooner than
    # a full-width card does.
    ".toolbar-right": {"gap", "font-size", "color", "flex-direction"},
}


@pytest.fixture(scope="module")
def css() -> str:
    """The stylesheet with comments stripped.

    Stripped first, not per-match: these comments discuss the very
    selectors being matched (`.filter-actions` appears in three of
    them), and a selector regex whose `[^{]*` can cross a newline will
    happily start inside one comment and end at an unrelated rule's
    brace. That produced a false positive on the first run of this
    file, which is a decent argument for the stripping.
    """
    return re.sub(r"/\*.*?\*/", "", BASE.read_text(encoding="utf-8"),
                  flags=re.S)


def _rule(css: str, selector: str) -> str:
    """The declaration block for an exact selector."""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.S)
    assert m, f"no rule for {selector!r}"
    return m.group(1)


def test_the_base_rule_is_unscoped(css: str) -> None:
    """Unscoped is the whole mechanism: a scoped base is just a fourth
    copy, and a move out of that scope loses it again."""
    assert re.search(r"\n\s*\.filter-row \{", css), (
        "no unscoped `.filter-row` base rule"
    )
    assert re.search(r"\n\s*\.filter-actions \{", css), (
        "no unscoped `.filter-actions` base rule"
    )


def test_the_base_carries_the_declarations_two_bugs_rediscovered(
    css: str,
) -> None:
    actions = _rule(css, "\n      .filter-actions")
    for decl in ("align-items: center", "justify-content: flex-end",
                 "margin-top: var(--space-3)", "flex-wrap: wrap"):
        assert decl in actions, f"the base lost `{decl}`"

    row = _rule(css, "\n      .filter-row")
    assert "display: flex" in row


def test_the_generic_label_rule_outranks_the_global_label_rule(
    css: str,
) -> None:
    """`body.ui-v2 label` is (0,1,2) and sets `display: block`. A bare
    `.filter-row > label` is (0,1,1) and loses to it, which un-stacks
    every label from its input — and blockifies the select, which is
    only `display: block` by virtue of being a flex item. Measured in
    Chromium when the base first landed without the prefix.
    """
    assert re.search(r"body\.ui-v2 \.filter-row > label \{", css), (
        "the generic label rule lost its `body.ui-v2` prefix and with it "
        "the specificity to beat `body.ui-v2 label`"
    )
    # ...and the prefix must NOT spread: at (0,3,2) a prefixed
    # `.filter-row > label.filter-search` outranks
    # `.operator-actions-card .filter-row > label.filter-search` (0,3,1)
    # and silently undoes that scope's only narrowing.
    for cls in ("filter-status", "filter-search"):
        assert not re.search(
            rf"body\.ui-v2 \.filter-row > label\.{cls} \{{", css
        ), (
            f"`.{cls}` base rule gained a `body.ui-v2` prefix; it now "
            "outranks the per-scope narrowings"
        )


@pytest.mark.parametrize("scope", sorted(ALLOWED_NARROWINGS))
def test_no_scope_redeclares_what_the_base_owns(css: str, scope: str) -> None:
    """The trap, stated as a test. A scope re-stating a base property is
    how the four-copy shape grew in the first place."""
    pattern = re.escape(scope) + r"[^{\n]*\.filter-(?:row|actions)[^{]*\{(.*?)\}"
    for m in re.finditer(pattern, css, re.S):
        block = m.group(1)
        for prop in BASE_OWNED:
            assert not re.search(rf"\b{re.escape(prop)}\s*:", block), (
                f"{scope} re-declares `{prop}`, which the base owns. "
                f"Either it is redundant, or it is an undocumented "
                f"divergence. Block: {block!r}"
            )


def test_every_scope_narrowing_is_one_the_list_accounts_for(
    css: str,
) -> None:
    """A narrowing nobody wrote down is the start of the next drift."""
    for scope, allowed in ALLOWED_NARROWINGS.items():
        pattern = (
            re.escape(scope) + r"[^{\n]*\.filter-(?:row|actions)[^{]*\{(.*?)\}"
        )
        for m in re.finditer(pattern, css, re.S):
            block = m.group(1)
            props = {
                p.strip() for p in re.findall(r"([a-z-]+)\s*:", block)
            }
            unexpected = props - allowed
            assert not unexpected, (
                f"{scope} narrows {sorted(unexpected)}, which "
                f"ALLOWED_NARROWINGS does not account for. Add it with a "
                f"reason, or move the declaration to the base."
            )
