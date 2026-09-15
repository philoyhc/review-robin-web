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
BASE_OWNED = (
    "align-items", "justify-content", "flex-wrap", "margin-top",
    "width", "box-sizing",
)

#: Every scope allowed to carry a `.filter-row` / `.filter-actions`
#: rule at all. A FOURTH scope is the direction the four-copy shape
#: actually grew from, and `ALLOWED_NARROWINGS` cannot see it — that
#: list only describes scopes someone already added to it.
KNOWN_SCOPES = {".filter-card", ".operator-actions-card", ".toolbar-right"}

#: What each scope is allowed to narrow, and why. Adding to this list is
#: a deliberate act; that is the point of it being a list.
ALLOWED_NARROWINGS = {
    ".filter-card": set(),                       # narrows nothing
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


def _filter_rows(markup: str) -> list[str]:
    """Each `.filter-row`'s inner markup, div-balanced.

    A non-greedy `.*?</div>` stops at the first close tag, which is
    inside the row; a greedy one runs past the row's own close into the
    confirm-checkbox label below it. Both were tried. Count the tags.
    """
    rows: list[str] = []
    for m in re.finditer(r'<div class="filter-row">', markup):
        start, depth = m.end(), 1
        for tag in re.finditer(r"<div\b|</div>", markup[m.end():]):
            depth += 1 if tag.group(0) != "</div>" else -1
            if depth == 0:
                rows.append(markup[start:m.end() + tag.start()])
                break
    return rows


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


def test_the_control_rules_outrank_the_global_control_rules(
    css: str,
) -> None:
    """The same specificity trap as the label rule, one rule over, and
    it shipped before it was spotted.

    `body.ui-v2 input[type="text"], …, body.ui-v2 select` is
    (0,2,2)/(0,1,2) and outranks a bare `.filter-row input[type="text"]`
    (0,2,1) / `.filter-row select` (0,1,1). It happens to set the SAME
    `width` and `box-sizing`, so nothing renders differently and a
    computed-style parity check cannot see it either — the rules are
    simply inert, and the base does not own what it claims to. The day
    that global rule changes, every strip follows it.
    """
    for control in ("select", 'input\[type="text"\]'):
        assert re.search(rf"body\.ui-v2 \.filter-row {control}", css), (
            f"the base `.filter-row {control}` rule has no `body.ui-v2` "
            "prefix, so the app-wide control rule outranks it and the "
            "base declaration is inert"
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


def test_no_fourth_scope_has_grown_its_own_copy(css: str) -> None:
    """The direction the shape actually drifted, and the one
    `ALLOWED_NARROWINGS` is blind to.

    That list only describes scopes someone has already written into
    it, so it rots by ADDITION: a new `.some-card .filter-actions`
    block is checked by nothing. This enumerates every rule in the
    stylesheet that selects the shape and asserts each one is either
    the base or a scope this file knows about.
    """
    seen: set[str] = set()
    for m in re.finditer(r"(?m)^\s*([^{}\n]*?\.filter-(?:row|actions)[^{}\n]*?)\s*\{", css):
        selector = m.group(1).strip()
        # The base rules themselves: they start with the class, or with
        # the `body.ui-v2` prefix the specificity note above explains.
        stripped = selector.replace("body.ui-v2 ", "", 1).strip()
        if stripped.startswith(".filter-row") or stripped.startswith(".filter-actions"):
            continue
        owner = next((s for s in KNOWN_SCOPES if s in selector), None)
        assert owner, (
            f"a rule outside every known scope selects the filter strip: "
            f"{selector!r}. Either fold it into the base, or add its scope "
            f"to KNOWN_SCOPES and ALLOWED_NARROWINGS with a reason."
        )
        seen.add(owner)
    assert seen <= KNOWN_SCOPES


def test_every_filter_row_label_is_classed() -> None:
    """The invariant that makes `.filter-card` narrowing nothing safe.

    It used to carry `flex: 1` on the generic label and the base does
    not, which is harmless only because every `<label>` in a
    `.filter-row` carries `.filter-status` or `.filter-search`, so the
    generic rule was always overridden. An unclassed label added later
    goes from `flex: 1 1 0` to `flex: 0 1 auto` — a layout change with
    nothing to catch it. Read from the templates, so it covers the
    pages a rendered fixture would not reach.
    """
    root = Path("app/web/templates/operator")
    checked = 0
    for path in sorted(root.glob("session_*.html")):
        markup = path.read_text(encoding="utf-8", errors="replace")
        for row in _filter_rows(markup):
            for label in re.finditer(r"<label\b([^>]*)>", row):
                attrs = label.group(1)
                checked += 1
                assert re.search(
                    r'class="[^"]*\bfilter-(?:status|search)\b', attrs
                ), (
                    f"{path.name}: a `.filter-row` label carries neither "
                    f"`.filter-status` nor `.filter-search`, so it falls "
                    f"back to `flex: 0 1 auto`: <label{attrs}>"
                )
    assert checked >= 7, f"vacuity: only {checked} labels found"
