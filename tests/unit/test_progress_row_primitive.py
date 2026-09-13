"""``.rs-progress-row`` owns its layout in ``base.html``.

`NF-23`'s neighbourhood. The class and its `.rs-instrument-progress`
child existed as **hooks with no CSS anywhere** — not in `base.html`,
not in any page `<style>` block, not in `static/`. The layout they
imply was written inline at four render paths: the reviewer surface,
the operator Instruments card's Band 2 preview, and two JS string
builders that rebuild the markup on every Band 3 edit.

`CLAUDE.md` → Templating conventions: *"When adding new visual
primitives, add a class to `base.html` rather than inline styles on
individual templates."* A class with no rule inverts that — it is a
name someone must remember to style again at each site, and four
copies is what happens when they do.

These tests pin the move. The integration tests in
``test_instrument_builder_routes.py`` assert the markup carries the
class and no inline ``style``; this asserts the class actually paints.
"""

from __future__ import annotations

from ._base_css import css, rules


def _declarations_for(selector_fragment: str) -> str:
    return " ".join(
        body
        for selector, body in rules(css())
        if selector_fragment in selector
    )


def test_progress_row_has_a_rule_at_all() -> None:
    assert _declarations_for(".rs-progress-row"), (
        ".rs-progress-row has no rule in base.html — it would be a "
        "class hook with no CSS, which is what this test exists to stop"
    )


def test_progress_row_carries_the_layout_that_used_to_be_inline() -> None:
    """The five declarations the four inline copies hardcoded."""
    decls = _declarations_for(".rs-progress-row")
    for declaration in (
        "display: flex",
        "flex-wrap: wrap",
        "justify-content: flex-end",
        "align-items: baseline",
    ):
        assert declaration in decls, f"missing: {declaration}"


def test_progress_row_spacing_uses_tokens_not_the_old_pixels() -> None:
    """The inline copies wrote ``gap: 12px`` and ``margin: 0 0 8px 0``.
    ``--space-3`` is 12px and ``--space-2`` is 8px, so the token form
    renders identically — that equivalence is why this was a move and
    not a restyle, and it is worth pinning rather than remembering.
    """
    decls = _declarations_for(".rs-progress-row")
    assert "gap: var(--space-3)" in decls
    assert "margin: 0 0 var(--space-2) 0" in decls
    assert "12px" not in decls and "8px" not in decls


def test_instrument_progress_child_has_its_rule_too() -> None:
    """``margin: 0`` was the fourth inline copy's whole contribution."""
    decls = _declarations_for(".rs-instrument-progress")
    assert decls, ".rs-instrument-progress has no rule in base.html"
    assert "margin: 0" in decls
