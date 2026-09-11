"""Session-nav hover wears the selected tab's colours — 2026-09-11.

Author: *"the hover over style for the setup and operations tabs are
different from that for Session home tab. standardize to — mouse hover
over style = tab selected style"*.

They were different in a way no template diff would show: the tab strip
hovered to a literal `rgba(255, 255, 255, 0.7)` while every other nav
colour came from a theme token. Seventy per cent white reads as a
tinted near-white over the light strips and as a glaring pale block
over the dark ones, because a literal cannot follow the theme.

Structural assertions over the stylesheet, in the idiom
``test_column_visibility_primitive.py`` set: nothing in a Python suite
renders CSS, so what can be checked is that the rule says what it is
supposed to say — and that the literal has not crept back.
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "web"
    / "templates"
    / "base.html"
)
CSS = BASE.read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    """The declaration block for one selector, whitespace-collapsed."""
    start = CSS.index(selector)
    body = CSS[CSS.index("{", start) + 1 : CSS.index("}", start)]
    return " ".join(body.split())


def test_the_tab_strip_no_longer_hovers_to_a_hardcoded_white() -> None:
    """The literal this change removed. Asserted by absence from the
    declarations rather than from the file, because the comment that
    explains the change quotes it."""
    for selector in (
        '.nav-tab:not(.disabled):not([aria-disabled="true"]):hover',
        'body.ui-v2 .nav-tab:not(.disabled):not([aria-disabled="true"]):hover',
    ):
        assert "rgba(255, 255, 255" not in _rule(selector), selector


def test_tab_hover_takes_the_selected_background() -> None:
    rule = _rule('.nav-tab:not(.disabled):not([aria-disabled="true"]):hover')
    assert "background: var(--nav-tab-active-bg);" in rule
    assert "color: var(--nav-tab-active-fg);" in rule


def test_v2_tab_hover_matches_the_v2_selected_tab() -> None:
    """v2's ``.nav-tab.active`` overrides only the colour and inherits
    v1's background, so hover has to do the same or the two versions
    disagree about what "selected" looks like."""
    hover = _rule(
        'body.ui-v2 .nav-tab:not(.disabled):not([aria-disabled="true"]):hover'
    )
    active = _rule("body.ui-v2 .nav-tab.active")
    assert "background: var(--nav-tab-active-bg);" in hover
    assert "color: var(--text-body);" in hover
    assert "color: var(--text-body);" in active


def test_the_home_anchor_hover_matches_its_own_selected_style() -> None:
    """Both versions, because the anchor's selected background differs
    between them — v1 uses the shared tab token, v2 the page surface."""
    assert "background: var(--nav-tab-active-bg);" in _rule(
        ".session-home-anchor:hover"
    )
    assert "background: var(--nav-tab-active-bg);" in _rule(
        ".session-home-anchor.active"
    )
    assert "background: var(--surface-page);" in _rule(
        "body.ui-v2 .session-home-anchor:hover"
    )
    assert "background: var(--surface-page);" in _rule(
        "body.ui-v2 .session-home-anchor.active"
    )


def test_a_disabled_tab_is_excluded_from_hover() -> None:
    """Not a tidy-up: ``body.ui-v2 .nav-tab:hover`` is specificity
    (0,3,1) and ``.nav-tab.disabled:hover`` is (0,3,0), so the disabled
    guard has been losing on every v2 page. The ``:not()`` pair settles
    it by never matching, rather than by out-ranking."""
    for selector in (
        ".nav-tab:not(.disabled):not(",
        "body.ui-v2 .nav-tab:not(.disabled):not(",
    ):
        assert selector in CSS, selector
    # And no unguarded hover rule survives to re-open the hole.
    assert not re.search(r"\.nav-tab:hover\s*\{", CSS)
    assert not re.search(r"body\.ui-v2 \.nav-tab:hover\s*\{", CSS)


def test_the_you_are_here_marker_stays_on_the_selected_tab_alone() -> None:
    """Hover matches the selected tab's *colours*, deliberately not its
    underline: paint that under the cursor and the operator cannot tell
    which page they are on while hovering."""
    assert ".nav-tab.active::after" in CSS
    assert not re.search(r"\.nav-tab[^\n{]*:hover::after\s*\{", CSS)
