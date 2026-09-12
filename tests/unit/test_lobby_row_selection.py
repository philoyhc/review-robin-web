"""A selection is marked by a bracket, not by a fill. Segment 19L Items 1-3.

19L.1 gave the selected row an edge and a fill. The fill was
``--row-selected-bg``, which resolves to the *same primitives as*
``--status-info-bg`` — and under ``body.ui-v2`` that token backs both
``.pill-count`` and ``.pill-info`` from one rule. A lobby row carries four
to six of those (Created by, Created, Deadline, Timezone, one per tag),
so on a selected row every one of them vanished, along with a Validated
status pill. Measured at 1.00 against the pill, where under ~1.15 a pill
has no visible boundary.

19L.2 removes the fill rather than replacing it. No other fill escapes:
the six pale pill fills occupy relative luminance 0.810-0.914 against a
1.000 card, so nothing fits above the band, and the only clearance below
it is dark enough to stop reading as a highlight. Instead the row takes a
rail at **each** end, and the injected action panel takes the same pair,
so the selection and the controls that act on it read as one bracket.
The retired fill's primitives move to that panel, where there are no
pills to erase.

19L.3 carries the same convention to the archived sessions page, which
19L.2 had deliberately left out: it injects a panel with the *same* class
names from its own script, so an unscoped rule would have given it the
closing half of a bracket whose rows were unmarked. It opts in now, by
the same class, with its own copy of the marking function — the two
scripts have diverged on purpose and a shared module built for its second
caller is the more expensive mistake to unwind.

**What these assert, and what they cannot.** The suite has no JavaScript
runtime, so nothing here proves a row *becomes* marked when ticked — that
was verified in Chromium against the rendered page, eight paths including
select-all (which fires no row change events) and the expander's own
Unselect-all / Unselect-others buttons (which fire synthetic ones). What
these hold is the **mechanism**: that the marking is wired into the one
funnel every selection path runs through, that the styles exist in both
themes, and that they are expressed with the tokens they claim. A test
that asserted ``"session-row-selected" in body`` would pass on every page
in the app, since ``base.html``'s CSS ships with every response — the
trap 19J.5 hit three times.

They also cannot see a rendered colour. Contrast ratios quoted above are
from the plan's measurements, not from anything checked here; a test that
cites a figure it does not check is not a check of that figure (19L.1).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOBBY = REPO / "app" / "web" / "templates" / "operator" / "sessions_list.html"
ARCHIVED = REPO / "app" / "web" / "templates" / "operator" / "sessions_archived.html"
BASE = REPO / "app" / "web" / "templates" / "base.html"

#: The class a selected row carries.
MARK = "session-row-selected"
#: The class the lobby's action panel opts in with.
BRACKET = "session-expander-bracketed"
#: Minimum rail width. A judgment, stated as one rather than derived:
#: there is no constant to read it off. A hairline on a full-width row
#: reads as one of the table's own rules rather than as a state. The
#: shipped value is 6px, doubled from 3px on the author's call once it
#: was seen rendered; this floor does not pin that figure, and
#: ``test_the_spec_and_the_stylesheet_agree_on_the_rail_width`` is what
#: stops the two drifting — an earlier version of this file asserted
#: only ``>= 2`` and let the spec sit at 3px while the app shipped 6px.
MIN_RAIL_PX = 2


def _lobby() -> str:
    return LOBBY.read_text()


def _base() -> str:
    return BASE.read_text()


def test_the_marking_is_wired_into_the_one_selection_funnel() -> None:
    """``refreshExpander`` is where every selection path already meets.

    A row tick, a select-all (which sets ``checked`` programmatically and
    fires no row events), and the expander's Unselect buttons all reach
    it. Marking anywhere else would cover some paths and not others —
    the defect 19L.1 fixed is itself an inconsistency of that kind.
    """
    body = _lobby()
    match = re.search(r"function refreshExpander\(\) \{(.*?)\n        \}", body, re.S)
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
    selected — worse than no marking at all, because it is confidently
    wrong.
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


def test_the_selected_row_has_a_rail_at_each_end() -> None:
    """Both ends, same token, same width, both inset shadows.

    One rail is 19L.1's design, which the fill accompanied. With the fill
    gone the row is marked at its extremes only, so losing either rail
    leaves a selected row signalled at one edge of a ~900px span.
    """
    css = _base()
    left = re.search(
        rf"tr\.{MARK} > td:first-child \{{\s*box-shadow: inset "
        r"(\d+)px 0 0 var\((--[a-z-]+)\);",
        css,
    )
    right = re.search(
        rf"tr\.{MARK} > td:last-child \{{\s*box-shadow: inset "
        r"-(\d+)px 0 0 var\((--[a-z-]+)\);",
        css,
    )
    assert left, "the selected row has no left rail"
    assert right, "the selected row has no right rail"
    assert left.group(2) == "--selected-bg", left.group(2)
    assert right.group(2) == "--selected-bg", right.group(2)
    assert left.group(1) == right.group(1), (
        f"the rails differ in width ({left.group(1)}px vs "
        f"{right.group(1)}px); they read as one bracket only if they match"
    )
    assert int(left.group(1)) >= MIN_RAIL_PX, (
        "a 1px rail on a full-width row reads as a table rule, not as a "
        "selected state"
    )


def test_the_selected_row_has_no_fill() -> None:
    """The 19L.2 defect, stated as the thing that must not come back.

    A background on the selected row is what erased its pills. Any fill
    in this palette does: the pale pill band has no clearance above it
    and only a too-dark clearance below.
    """
    css = _base()
    block = re.search(rf"tr\.{MARK} > td \{{(.*?)\}}", css, re.S)
    assert block is None, (
        "the selected row has a `> td` rule again — if it sets a "
        "background, every .pill-count and .pill-info on the row goes "
        "invisible, which is the defect 19L.2 removed:\n"
        f"{block.group(0) if block else ''}"
    )
    assert "--row-selected-bg:" not in css, (
        "--row-selected-bg is declared again; it was renamed to "
        "--selection-panel-bg when the fill moved off the row"
    )


def test_the_rails_do_not_change_the_row_height() -> None:
    """Inset shadows, never borders.

    A border on selection would add its width to the row and reflow the
    table under the operator's pointer at the moment they are aiming at
    a destructive control. This is also why the bracket has no top or
    bottom cap: the author declined them on that ground, 2026-09-12.
    """
    css = _base()
    for selector in (
        rf"tr\.{MARK} > td:first-child",
        rf"tr\.{MARK} > td:last-child",
        rf"\.{BRACKET} > td",
    ):
        block = re.search(rf"{selector} \{{(.*?)\}}", css, re.S)
        assert block, f"the rule for {selector} is gone"
        assert "border" not in block.group(1), (
            f"{selector} draws its rail with a border, which changes the "
            "row's height on selection; use an inset box-shadow"
        )


def test_the_panel_closes_the_bracket_and_opts_in_by_class() -> None:
    """The panel takes both rails, and the class is what grants them.

    ``sessions_archived.html`` injects a panel carrying the *same*
    ``session-expander session-expander-bulk`` classes from its own
    script. A rule on ``.session-expander`` alone would style both pages
    at once, which is why the bracket is opt-in.

    **The reason changed under this test, and the test changed with it.**
    Until 19L.3 it asserted that the archived page did *not* carry the
    class, because that page marked no rows and would have rendered the
    closing half of a bracket with no opening half. 19L.3 gave it the
    marking, so it now opts in too — see
    ``test_the_archived_page_follows_the_same_convention``. The class is
    still the gate; what it gates is now two pages rather than one.
    Written out rather than deleted: a guard that vanishes takes its
    reason with it, and the next person to wonder why this is opt-in at
    all would have nothing to read.
    """
    css = _base()
    block = re.search(rf"\.{BRACKET} > td \{{(.*?)\}}", css, re.S)
    assert block, f".{BRACKET} has no rule — the panel does not close the bracket"
    rule = block.group(1)
    assert rule.count("inset") == 2, (
        "the panel's cell is both first and last child, so it needs both "
        f"rails in one declaration; found {rule.count('inset')}"
    )
    assert "var(--selected-bg)" in rule, "the panel's rails are not --selected-bg"
    # Added after a mutation escaped: reverting the panel to
    # --surface-muted — undoing half of 19L.2 — passed all ten tests,
    # because every one of them checked the rails and none checked the
    # interior. The fill is not decoration here: it is where the row's
    # retired fill went, and it is what lifts the panel's own inputs and
    # buttons off 1.09 against their background.
    assert "background: var(--selection-panel-bg);" in rule, (
        "the bracket's panel no longer fills with --selection-panel-bg, "
        "so the bracket encloses nothing and the panel's inputs and "
        "buttons are back to being legible only by their borders"
    )

    lobby = _lobby()
    assert lobby.count(BRACKET) == 2, (
        f"expected both lobby expander templates to carry .{BRACKET}; "
        f"found {lobby.count(BRACKET)}"
    )
    assert ARCHIVED.read_text().count(BRACKET) == 1, (
        "the archived sessions page's single bulk expander should carry "
        f".{BRACKET} exactly once (19L.3)"
    )


def test_the_panel_fill_is_its_own_role_in_both_themes() -> None:
    """``--selection-panel-bg`` is declared light and dark.

    It resolves to the same primitives as ``--chip-selected-bg`` today.
    It exists anyway because a panel and a chip are different roles, and
    a repoint of one should not silently move the other — the two-tier
    system's whole argument.
    """
    css = _base()
    declarations = re.findall(r"--selection-panel-bg:\s*var\((--[a-z-]+)\);", css)
    assert len(declarations) == 2, (
        f"--selection-panel-bg is declared {len(declarations)} time(s); it "
        "needs one declaration per theme or one theme renders the other "
        "theme's fill"
    )
    assert declarations[0] != declarations[1], (
        "both themes point --selection-panel-bg at the same primitive, so "
        "one of them is wrong: a pale light fill is not a dark one"
    )


def test_the_panel_is_recorded_as_a_pill_free_zone() -> None:
    """The condition the panel's fill creates, kept next to the fill.

    ``--selection-panel-bg`` resolves to ``--status-info-bg``'s own
    primitives. That is safe only while the panel renders no pill; a
    ``.pill-count`` added there later reopens exactly the collision the
    token was moved off the row to escape. Nothing in a stylesheet can
    detect a pill that a future template renders, so what is guarded is
    that the warning is still *present where the next author will read
    it* — a weaker thing than a check, and stated as such.
    """
    css = _base()
    block = re.search(
        r"/\*[^*]*(?:\*(?!/)[^*]*)*\*/\s*--selection-panel-bg: var\(--blue-pale\);",
        css,
    )
    assert block, "--selection-panel-bg lost the comment above its declaration"
    assert "PILL-FREE ZONE" in block.group(0), (
        "the note warning that this token's primitives are "
        "--status-info-bg's, so the panel must render no pills, is gone "
        "from the declaration a future author will edit"
    )


def test_the_field_label_resets_the_global_label_margin() -> None:
    """The panel's rhythm is its flex gap, not the gap plus a margin.

    ``body.ui-v2 label`` sets ``margin: var(--space-3) 0 var(--space-1)
    0``. ``.session-expander-fields label`` declares display, gap, font
    and flex but, until 19L.2, no margin — so the global margin still
    reached it per property and stacked 12px onto
    ``.session-expander-body``'s 12px flex gap, putting the field row
    24px below the title. ``.exp-allow-delete`` two rules away already
    carried the reset, with a comment naming this hazard.
    """
    css = _base()
    block = re.search(
        r"\.session-expander-fields label \{(.*?)\}", css, re.S
    )
    assert block, ".session-expander-fields label has no rule"
    assert re.search(r"margin:\s*0\s*;", block.group(1)), (
        "the expander's field label no longer resets the global "
        "body.ui-v2 label margin, so its 12px top margin stacks on the "
        "panel's 12px flex gap and the field row sits 24px below the "
        "title in a panel whose stated rhythm is 12px"
    )


def test_the_spec_and_the_stylesheet_agree_on_the_rail_width() -> None:
    """Two places state the rail's width; neither may drift from the other.

    This guard exists because they did. 19L.1 doubled the edge from 3px
    to 6px in ``base.html`` and in this file's floor, and left
    ``spec/ui_elements.md`` saying ``inset 3px`` — undetected for a day,
    because the test asserted a range rather than the figure. A range
    cannot pin a number.
    """
    css = _base()
    shipped = re.search(
        rf"tr\.{MARK} > td:first-child \{{\s*box-shadow: inset (\d+)px", css
    )
    assert shipped, "cannot read the shipped rail width"
    width = shipped.group(1)

    spec = (REPO / "spec" / "ui_elements.md").read_text()
    row = next(
        (line for line in spec.splitlines() if f"`.{MARK}`" in line),
        None,
    )
    assert row, f"spec/ui_elements.md no longer documents .{MARK}"
    quoted = re.findall(r"inset (?:-)?(\d+)px", row)
    assert quoted, (
        "spec/ui_elements.md documents the selected row but states no "
        "rail width, so the two cannot be checked against each other"
    )
    assert set(quoted) == {width}, (
        f"the stylesheet ships a {width}px rail; spec/ui_elements.md "
        f"states {sorted(set(quoted))}px"
    )


def _archived() -> str:
    return ARCHIVED.read_text()


def test_the_archived_page_follows_the_same_convention() -> None:
    """19L.3 — the sibling page marks rows and closes its bracket.

    The two pages are reached from one another and render the same table
    shape, so selecting differently on each is the inconsistency this
    item removed. The page needed no new CSS: 19L.2's rules were already
    written against the opt-in class.
    """
    body = _archived()
    match = re.search(
        r"function refreshExpander\(\) \{(.*?)\n        \}", body, re.S
    )
    assert match, "refreshExpander() not found — the archived script moved"
    assert "markSelectedRows(" in match.group(1), (
        "the archived page's refreshExpander no longer marks its selected "
        "rows, so its select-all — which fires no row change events — "
        "would inject a panel while leaving every row unmarked"
    )
    assert BRACKET in body, (
        f"the archived page's expander no longer carries .{BRACKET}, so "
        "its panel does not close the bracket its rows now open"
    )


def test_the_archived_marking_clears_before_it_applies() -> None:
    """The same ordering the lobby needs, asserted on its own copy.

    Duplicated code needs duplicated guards: a shared assertion over one
    of the two would let the other rot silently, which is the cost this
    item accepted when it chose duplication over a shared module.
    """
    body = _archived()
    match = re.search(
        r"function markSelectedRows\(selected\) \{(.*?)\n        \}", body, re.S
    )
    assert match, "markSelectedRows() not found on the archived page"
    fn = match.group(1)
    clear_at = fn.find(f'classList.remove("{MARK}")')
    apply_at = fn.find(f'classList.add("{MARK}")')
    assert clear_at != -1, "nothing clears the mark on the archived page"
    assert apply_at != -1, "nothing applies the mark on the archived page"
    assert clear_at < apply_at, (
        "the archived page applies the mark before the sweep that clears "
        "it, so the sweep would erase the row it just marked"
    )


def test_the_archived_marking_runs_before_the_empty_early_return() -> None:
    """Un-ticking the last row must clear the marks, not leave one behind.

    ``refreshExpander`` returns early when nothing is selected. If the
    marking sits after that return, the final un-tick removes the panel
    and leaves the row still bracketed — confidently wrong, which is
    worse than unmarked. The lobby is covered by the same ordering; this
    pins the copy.
    """
    body = _archived()
    match = re.search(
        r"function refreshExpander\(\) \{(.*?)\n        \}", body, re.S
    )
    assert match, "refreshExpander() not found — the archived script moved"
    fn = match.group(1)
    mark_at = fn.find("markSelectedRows(selected)")
    return_at = fn.find("if (selected.length === 0) return;")
    assert mark_at != -1 and return_at != -1, fn
    assert mark_at < return_at, (
        "markSelectedRows runs after the empty-selection early return, so "
        "un-ticking the last row leaves it marked with no panel"
    )


def test_the_archived_panel_hosts_no_pill() -> None:
    """The pill-free-zone condition, enforced where it is now load-bearing.

    ``--selection-panel-bg`` is ``--status-info-bg``'s own primitive, so
    a ``.pill-count`` inside a bracketed panel would be invisible against
    it — the 19L.2 collision, one storey down. Both pages' panels are in
    scope; the archived page's rows carry four ``.pill-count``s and a
    lifecycle pill, which is exactly the material that must not migrate
    into the panel.

    The author stated the condition as part of the design: *"action row
    should not host any pills."*
    """
    for name, body in (("archived", _archived()), ("lobby", _lobby())):
        for match in re.finditer(
            r"<template[^>]*>(.*?)</template>", body, re.S
        ):
            block = match.group(1)
            if BRACKET not in block:
                continue
            assert "pill" not in block, (
                f"a bracketed expander template on the {name} page renders "
                "a pill. Its background is --status-info-bg\'s primitive, "
                "so the pill has no visible boundary — the collision 19L.2 "
                "moved that token off the row to escape"
            )
