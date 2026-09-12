"""A selected lobby row is marked, not just its panel. Segment 19L Item 1.

Before this, the only row-level signal that a session was selected was
its own checkbox tick — a ~13px mark at one end of a full-width row. The
injected action panel tinted its own ``<td>``; no class ever reached the
source ``<tr>``. That is adequate at the instant of clicking and weakest
exactly where the lobby invites it: a bulk selection scattered down the
table, a tall panel pushing the row off-screen, a page returned to.

**What these assert, and what they cannot.** The suite has no JavaScript
runtime, so nothing here proves a row *becomes* marked when ticked —
that was verified in Chromium against the rendered page, eight paths
including select-all (which fires no row change events) and the
expander's own Unselect-all / Unselect-others buttons (which fire
synthetic ones). What these tests hold is the **mechanism**: that the
marking is wired into the one funnel every selection path runs through,
that the style exists in both themes, and that it is expressed with the
tokens it claims. A test that asserted `"session-row-selected" in body`
would pass on every page in the app, since `base.html`'s CSS ships with
every response — the trap 19J.5 hit three times.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOBBY = REPO / "app" / "web" / "templates" / "operator" / "sessions_list.html"
BASE = REPO / "app" / "web" / "templates" / "base.html"

#: The class the row carries while selected.
MARK = "session-row-selected"


def _lobby() -> str:
    return LOBBY.read_text()


def _base() -> str:
    return BASE.read_text()


def test_the_marking_is_wired_into_the_one_selection_funnel() -> None:
    """``refreshExpander`` is where every selection path already meets.

    A row tick, a select-all (which sets ``checked`` programmatically and
    fires no row events), and the expander's Unselect buttons all reach
    it. Marking anywhere else would cover some paths and not others —
    the defect being fixed is itself an inconsistency of that kind.
    """
    body = _lobby()
    match = re.search(
        r"function refreshExpander\(\) \{(.*?)\n        \}", body, re.S
    )
    assert match, "refreshExpander() not found — the lobby script moved"
    assert "markSelectedRows(" in match.group(1), (
        "refreshExpander no longer marks the selected rows, so a "
        "select-all — which fires no row change events — would inject a "
        "panel while leaving every row unmarked."
    )


def test_the_marking_clears_before_it_applies() -> None:
    """Every row is cleared each pass, not only the one being un-ticked.

    Without the clear, un-ticking via any path that does not fire that
    row's own handler leaves a stale mark on a row that is no longer
    selected — which is worse than no marking at all, because it is
    confidently wrong.
    """
    body = _lobby()
    match = re.search(
        r"function markSelectedRows\(selected\) \{(.*?)\n        \}", body, re.S
    )
    assert match, "markSelectedRows() not found"
    fn = match.group(1)
    clear_at = fn.find(f'classList.remove("{MARK}")')
    apply_at = fn.find(f'classList.add("{MARK}")')
    assert clear_at != -1, "nothing clears the mark"
    assert apply_at != -1, "nothing applies the mark"
    assert clear_at < apply_at, (
        "the mark is applied before the sweep that clears it, so the "
        "sweep would erase the row it just marked"
    )


def test_the_row_style_carries_both_an_edge_and_a_fill() -> None:
    """Candidate D: what ``.tag-chip.is-selected`` already does.

    The reserved shade as an edge, its pale companion as the interior.
    Either half alone is a different candidate that was considered and
    not chosen, so a rule that lost one is a silent change of design.
    """
    css = _base()
    fill = re.search(
        rf"tr\.{MARK} > td \{{\s*background: var\((--[a-z-]+)\);", css
    )
    edge = re.search(
        rf"tr\.{MARK} > td:first-child \{{\s*box-shadow: inset "
        r"(\d+)px 0 0 var\((--[a-z-]+)\);",
        css,
    )
    assert fill, "the selected row has no fill rule"
    assert edge, "the selected row has no edge rule"
    assert fill.group(1) == "--row-selected-bg", fill.group(1)
    assert edge.group(2) == "--selected-bg", edge.group(2)
    assert int(edge.group(1)) >= 2, (
        "the edge is thinner than the 2px a selected chip carries"
    )


def test_the_edge_does_not_change_the_row_height() -> None:
    """An inset shadow, never a border.

    A border on selection would add its width to the row and reflow the
    table under the operator's pointer at the moment they are aiming at
    a destructive control.
    """
    css = _base()
    block = re.search(
        rf"tr\.{MARK} > td:first-child \{{(.*?)\}}", css, re.S
    )
    assert block, "the edge rule is gone"
    assert "border" not in block.group(1), (
        "the selected-row edge is drawn with a border, which changes the "
        "row's height on selection; use an inset box-shadow"
    )


def test_the_row_token_is_its_own_role_in_both_themes() -> None:
    """``--row-selected-bg`` is declared light and dark.

    It resolves to the same primitives as ``--chip-selected-bg`` today.
    It exists anyway because a row and a chip are different roles, and a
    repoint of one should not silently move the other — the two-tier
    system's whole argument.
    """
    css = _base()
    declarations = re.findall(r"--row-selected-bg:\s*var\((--[a-z-]+)\);", css)
    assert len(declarations) == 2, (
        f"--row-selected-bg is declared {len(declarations)} time(s); it "
        "needs one declaration per theme or one theme renders the other "
        "theme's fill"
    )
    assert declarations[0] != declarations[1], (
        "both themes point --row-selected-bg at the same primitive, so "
        "one of them is wrong: a pale light fill is not a dark one"
    )
