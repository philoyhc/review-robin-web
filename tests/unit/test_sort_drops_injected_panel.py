"""A client-side sort drops the injected selection panel — 19O Item 4.

``_rrwApplySort`` re-sorts **every child** of ``tbody.rrw-rows``. An
injected ``.session-expander`` panel is one of those children, carries a
single ``colspan`` cell and no ``data-sort-value``, so ``_rrwCellValue``
returns ``null`` for every column and the null-last rule parks it at the
bottom of the table, detached from the row it brackets.

The second effect is quieter and worse. The same pass stamps
``rrwOriginalIndex`` once per row, which is what ``state.length === 0``
restores when the operator clears the sort. A panel present at stamping
time occupies an index, so **every row after it is stamped one too
high** and "unsorted" stops restoring the server's order.

**There is no JS runtime in this suite**, so these are structural
assertions over the shipped source, in the idiom of
``test_column_visibility_primitive.py``. They pin the mechanism — the
removal, its position relative to the stamp, the dispatch, and a
listener per owner — because the browser half is confirmed on the dev
slot and nothing here can reach it.

The ordering assertion is the load-bearing one. A removal that ran
*after* the stamp would leave the index corruption in place while
looking correct in a grep, which is exactly the class of guard 19P kept
having to re-aim: one that proves less than it claims.

Two things here are shaped by that class of failure recurring inside
this very module. The page set is **derived** from the templates rather
than listed, because a hand-maintained list is an un-pinned
measurement; and the second-mechanism guard asserts a **property** —
that these pages touch ``rrw-sort-btn`` in markup only — rather than
the byte-shape of the handler it is hunting, because two earlier drafts
that guessed at a spelling were both defeated by a spelling nobody had
guessed.
"""
from __future__ import annotations

import re

from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
BASE = TEMPLATES / "base.html"
OPERATOR = TEMPLATES / "operator"

#: `sessions_list.html` is the one page with a *legitimate* script-side
#: `.rrw-sort-btn` reference: Item 4's unsaved-edit confirm gates the
#: sort click rather than removing anything. Every other sorting page
#: that injects a panel should have no script-side reference at all, so
#: they get the blunt assertion and this one gets the careful one.
PAGE_WITH_A_SORT_BUTTON_HANDLER_OF_ITS_OWN = "sessions_list.html"

#: The census as it stands today, pinned so that a seventh page joining
#: it is a **test failure rather than a silent exemption**. The set the
#: other tests run over is derived from the templates (below), not from
#: this list; this is the assertion that the derivation still matches
#: what a human last looked at.
#:
#: `session_observers.html` injects a panel and declares no
#: `data-rrw-sortable`, so it needs neither half and is deliberately
#: absent. It is the whole difference between "seven templates inject"
#: and "six sort".
#:
#: A hand-maintained list was the first version of this, and a cold read
#: named it for what it was: an un-pinned measurement, the very thing
#: the comment three lines below it warns about. The plan's own blast
#: radius said *three* injecting pages, measured at `820d5d6`; 19P.2-3
#: and 19P.5 added four more between that measurement and the item being
#: built. *A measurement carries its commit for exactly this reason* —
#: and a derived set carries no commit at all, which is better.
EXPECTED_PAGES = {
    "sessions_list.html",
    "sessions_archived.html",
    "session_reviewers.html",
    "session_reviewees.html",
    "session_relationships.html",
    "session_assignments.html",
}


def _injects_and_sorts() -> list[str]:
    """Every operator template that injects a panel **and** sorts.

    Derived rather than listed: a page added later picks up both halves
    of this guard by existing, instead of by someone remembering to add
    a line here.
    """
    found = []
    for path in sorted(OPERATOR.glob("*.html")):
        src = path.read_text(encoding="utf-8")
        if "session-expander" not in src:
            continue
        if any(_declares_sortable(line) for line in src.splitlines()):
            found.append(path.name)
    return found


def _declares_sortable(line: str) -> bool:
    """Is this line a real `data-rrw-sortable` **attribute**?

    The `=` and the comment test are both load-bearing, and this
    function's first version had neither. `session_observers.html`
    mentions the attribute in a comment explaining why it has none
    (*"no `data-rrw-sortable`; `_list_observers` orders by id"*) and
    injects a panel, so a bare substring match pulls in the one page
    that is deliberately outside this guard — and `session_assignments`
    names it in a comment too. The pinned census caught exactly that on
    the first run, which is what it is for.
    """
    stripped = line.strip()
    if stripped.startswith("//") or stripped.startswith("{#"):
        return False
    return "data-rrw-sortable=" in stripped


def _script_text(src: str) -> str:
    """Just the `<script>` bodies, so page markup cannot satisfy a check.

    Every one of these templates renders `class="rrw-sort-btn"` on seven
    to thirteen `<th>` buttons, so any assertion about the *string*
    `rrw-sort-btn` over the whole file is about the header markup and
    not about a handler.
    """
    return "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", src, re.S))


def _strip_line_comments(js: str) -> str:
    """Blank out ``//`` comment text, keeping every byte's position.

    Written after this module's own first run failed: the ordering
    assertion matched ``rrwOriginalIndex`` inside the *comment* that
    explains the fix, 400 characters ahead of the code it describes.
    That is the same defect 19P kept re-aiming guards for — an
    assertion satisfied by prose the page happens to contain. Padding
    with spaces rather than deleting keeps every surviving index
    comparable to the raw source, so a failure message still points at
    a real offset.
    """
    out = []
    i = 0
    while i < len(js):
        if js.startswith("//", i):
            end = js.find("\n", i)
            if end == -1:
                end = len(js)
            out.append(" " * (end - i))
            i = end
        else:
            out.append(js[i])
            i += 1
    return "".join(out)


def _apply_sort_body() -> str:
    """``_rrwApplySort``'s source, brace to brace, comments blanked.

    Counted rather than regexed: the function contains nested braces in
    both its loops and its comparator, so a non-greedy match to the
    first ``}`` would stop inside the first ``if`` and a greedy one
    would run to the end of the file. Either would let a real
    regression pass.
    """
    src = _strip_line_comments(BASE.read_text(encoding="utf-8"))
    start = src.index("function _rrwApplySort(")
    open_brace = src.index("{", start)
    depth = 0
    for i in range(open_brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_brace : i + 1]
    raise AssertionError("_rrwApplySort is not brace-balanced")


#: `if (` looks exactly like a call to a regex and is not one. The
#: control-flow keywords that take a parenthesis are skipped so that
#: `if (expanderIsDirty())` reports the function rather than the `if`.
_NOT_A_CALL = frozenset(
    {"if", "for", "while", "switch", "catch", "return", "function", "typeof"}
)


def _first_call(js: str) -> str | None:
    """The first function actually invoked in ``js``, or ``None``."""
    for match in re.finditer(r"([A-Za-z_$][\w$.]*)\s*\(", js):
        name = match.group(1).split(".")[-1]
        if name not in _NOT_A_CALL:
            return name
    return None


def test_the_panel_is_removed_before_the_rows_are_stamped() -> None:
    """The ordering, which is the whole fix.

    Removal after the stamp would still strand the panel visually and
    would still corrupt `rrwOriginalIndex` — the defect this item exists
    for. Asserting only that a removal exists somewhere would pass on
    that broken arrangement.
    """
    body = _apply_sort_body()

    # The *removal*, not the selector. The first version of this test
    # indexed `.session-expander`, which pins where the panel is
    # `querySelectorAll`-ed and says nothing about where it leaves the
    # DOM. A cold read split the two statements — selector early,
    # `removeChild` after the stamp — and all four assertions passed
    # against an implementation that left the index corruption live and
    # re-appended the panel at the bottom from the stale `rows` array.
    removal = body.index("removeChild")
    collect = body.index("tbody.children")
    stamp = body.index("rrwOriginalIndex")

    assert removal < collect, (
        "the panel must leave the DOM before `tbody.children` is "
        "collected — otherwise it is sorted as a row"
    )
    assert removal < stamp, (
        "the panel must leave the DOM before `rrwOriginalIndex` is "
        "stamped — otherwise every row after it is stamped one too high "
        "and the unsorted restore order is corrupted"
    )


def test_the_panel_is_removed_rather_than_hidden() -> None:
    """A hidden row still occupies an `rrwOriginalIndex`.

    Aimed at what is removed, not merely that a `removeChild` appears:
    the bare-substring version would have passed on a `removeChild` of
    anything at all.
    """
    body = _apply_sort_body()

    # Ordering, not distance. A first draft asserted the `removeChild`
    # sat within 200 characters of the selector, which was a number
    # picked from the current 102 rather than derived from anything —
    # and `_strip_line_comments` pads comments with spaces, so three
    # explanatory lines inserted between the two would have failed the
    # test with a message about "removing something else" that was not
    # true. What actually matters is that the selector precedes the
    # removal and the removal precedes the stamp; the sibling test
    # above owns the second half.
    assert body.index(".session-expander") < body.index("removeChild"), (
        "the `removeChild` must act on the panels this function "
        "selected, so the selector comes first"
    )
    assert "style.display" not in body, (
        "the panel must leave the DOM; hiding it keeps its index"
    )


def test_the_sort_signals_after_the_rows_land() -> None:
    """A listener re-anchors against a row, so it needs the final order."""
    body = _apply_sort_body()

    dispatch = body.index('"rrw:sorted"')
    reappend = body.index("tbody.appendChild")

    assert reappend < dispatch, (
        "`rrw:sorted` must fire after the rows are re-appended, or a "
        "listener re-anchors against the pre-sort order"
    )


def test_the_page_census_is_still_the_one_a_human_checked() -> None:
    """A seventh sorting page must announce itself, not slip in.

    The two guards below run over the *derived* set, so a new page is
    covered automatically — but "covered" and "correct" are different
    claims, and nobody has read the new page. This failing is the
    prompt to read it and then widen `EXPECTED_PAGES`.
    """
    assert set(_injects_and_sorts()) == EXPECTED_PAGES, (
        "the set of operator templates that inject a `.session-expander` "
        "into a `data-rrw-sortable` table has changed; read the new or "
        "departed page against this module's two guards, then update "
        "`EXPECTED_PAGES`"
    )


@pytest.mark.parametrize("page", _injects_and_sorts())
def test_every_page_that_sorts_and_injects_listens(page: str) -> None:
    """The dispatch is only half a fix without an owner on the other end."""
    src = (OPERATOR / page).read_text(encoding="utf-8")
    assert 'addEventListener("rrw:sorted"' in src, (
        f"{page} injects a selection panel and sorts, so it must "
        "re-anchor on `rrw:sorted`"
    )


@pytest.mark.parametrize("page", _injects_and_sorts())
def test_no_page_keeps_a_second_mechanism(page: str) -> None:
    """One mechanism, now that the migration is complete.

    While the migration was in flight this asserted *at least* one,
    because a page carrying both is redundant rather than broken and
    failing it would have forced the two halves of a move into one
    commit. With every page migrated the weaker form has nothing left
    to permit, and the real risk is a page that keeps its old
    capture-phase handler beside the listener: the panel is removed
    twice and the page re-renders twice per sort.

    **Aimed at the reference, not at the workaround's shape.** A draft
    of this matched the historical handler's exact byte-shape — a
    `.rrw-sort-btn` guard, a newline, `if (panel)`. Run against nine
    plausible re-introductions it caught **one**: single quotes, a
    braced `return`, both statements on one line, a comment between
    them, a renamed variable, `panel && panel.remove()`, `panel !==
    null`, and — worst — a guard that only calls `render()` and removes
    nothing all walked straight past it. That last one is exactly the
    double-render this test names in its own failure message.

    So the assertion is now that these pages touch `rrw-sort-btn` in
    **markup only**. There is no legitimate script-side reason to look
    at a sort button on a page that listens for `rrw:sorted`, which
    makes the absence checkable without predicting the spelling.
    `sessions_list.html` is the single exception and is checked by its
    own test below, because its reference is a gate rather than a
    handler.
    """
    src = (OPERATOR / page).read_text(encoding="utf-8")
    assert 'addEventListener("rrw:sorted"' in src, f"{page} lost its listener"

    if page == PAGE_WITH_A_SORT_BUTTON_HANDLER_OF_ITS_OWN:
        # Returning rather than skipping: the listener assertion above
        # is real for this page too, and `CLAUDE.md` asks that skips be
        # read rather than counted — a skip here would report as a
        # tool-gated one and be worth nobody's attention.
        # `test_the_lobby_gate_stays_a_gate` owns the rest.
        return

    script = _strip_line_comments(_script_text(src))
    assert "rrw-sort-btn" not in script, (
        f"{page} looks at a sort button from script. The shared "
        "`rrw:sorted` listener is the whole mechanism now; a second one "
        "removes the panel twice and re-renders twice per sort. If this "
        "is a deliberate new gate rather than 19P.1's revived handler, "
        "it belongs beside the lobby's in "
        "`PAGE_WITH_A_SORT_BUTTON_HANDLER_OF_ITS_OWN`."
    )


def test_the_lobby_gate_stays_a_gate() -> None:
    """The lobby's `.rrw-sort-btn` reference may confirm, nothing else.

    `sessions_list.html` gates the sort click on Item 4's unsaved-edit
    confirm, so it cannot take the blanket assertion above — and being
    the one page allowed to look at a sort button from script, it is
    also the one page where 19P.1's handler could come back wearing a
    gate's clothes.

    **A whitelist, because the blacklist version failed its own mutation
    run.** The first draft forbade `remove(`, `render(` and `= null`
    within 240 characters. Injecting `refreshExpander();` — this page's
    actual panel rebuild, which is neither of those spellings — walked
    straight through it. Guessing the names a future handler will use is
    the defect this whole module keeps re-learning, so this asserts what
    is *allowed* instead: the first thing called after the guard returns
    must be the dirty check. Anything else fails, whatever it is called.
    """
    page = PAGE_WITH_A_SORT_BUTTON_HANDLER_OF_ITS_OWN
    script = _strip_line_comments(
        _script_text((OPERATOR / page).read_text(encoding="utf-8"))
    )

    hits = [m.start() for m in re.finditer("rrw-sort-btn", script)]
    assert hits, (
        f"{page}'s unsaved-edit gate is gone; either restore it or move "
        "this page under the blanket assertion above"
    )
    for at in hits:
        rest = script[at:]
        guard_end = re.search(r"\breturn\s*;", rest)
        assert guard_end is not None, (
            f"{page} references a sort button outside an early-return "
            "guard; the only sanctioned use here is Item 4's confirm"
        )
        called = _first_call(rest[guard_end.end() :])
        assert called == "expanderIsDirty", (
            f"{page} calls `{called}` first after its sort-button guard, "
            "where only `expanderIsDirty` belongs. `_rrwApplySort` drops "
            "the panel and fires `rrw:sorted`; a second opinion here is "
            "19P.1's handler by another name."
        )
